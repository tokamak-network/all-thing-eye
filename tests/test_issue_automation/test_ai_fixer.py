import pytest
from dataclasses import dataclass
from typing import Dict, List, Optional

from scripts.issue_automation.ai_fixer import AIFixer, FixResult, FixAction


@dataclass
class MockDiagnosisResult:
    member_found: bool
    member_name: Optional[str]
    github_username: str
    identifiers: Dict[str, List[str]]
    activities_found: Dict[str, int]
    issues: List[str]
    recommendations: List[str]


class TestAIFixer:
    @pytest.fixture
    def fixer(self):
        return AIFixer()

    @pytest.fixture
    def diagnosis_member_not_found(self):
        return MockDiagnosisResult(
            member_found=False,
            member_name=None,
            github_username="unknown_user",
            identifiers={},
            activities_found={},
            issues=["No member found with GitHub username 'unknown_user'"],
            recommendations=["Add GitHub identifier mapping for this user"],
        )

    @pytest.fixture
    def diagnosis_member_found_with_activities(self):
        return MockDiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={"github": ["testuser"], "slack": ["U12345"]},
            activities_found={"GitHub": 10, "Slack": 5},
            issues=[],
            recommendations=[],
        )

    @pytest.fixture
    def diagnosis_member_found_no_activities(self):
        return MockDiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={"github": ["testuser"]},
            activities_found={"GitHub": 0, "Slack": 0},
            issues=["No GitHub activities found in the last 30 days"],
            recommendations=["Check if data collection is running"],
        )

    @pytest.fixture
    def diagnosis_missing_identifier(self):
        return MockDiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={"github": ["testuser"]},
            activities_found={"GitHub": 10, "slack": 5},
            issues=[],
            recommendations=["Add slack identifier for Test User"],
        )

    def test_generate_identifier_insert_script(self, fixer):
        script = fixer.generate_identifier_insert_script(
            member_name="Test User",
            source="slack",
            identifier_value="U12345678",
        )

        assert "member_identifiers.insertOne" in script
        assert "Test User" in script
        assert "slack" in script
        assert "U12345678" in script

    def test_generate_fix_without_ai_member_not_found(
        self, fixer, diagnosis_member_not_found
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_not_found)

        assert isinstance(result, FixResult)
        assert "not found" in result.diagnosis_summary.lower()
        assert len(result.actions) > 0
        assert result.actions[0].action_type == "manual_check"
        assert "unknown_user" in result.actions[0].description

    def test_generate_fix_without_ai_member_found(
        self, fixer, diagnosis_member_found_with_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_with_activities)

        assert isinstance(result, FixResult)
        assert "Test User" in result.diagnosis_summary
        assert len(result.comment_body) > 0
        assert "Automated Diagnosis Report" in result.comment_body

    def test_generate_fix_without_ai_no_activities(
        self, fixer, diagnosis_member_found_no_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_no_activities)

        assert "GitHub: 0 activities found" in result.diagnosis_summary
        assert "Slack: 0 activities found" in result.diagnosis_summary

    def test_generate_fix_without_ai_missing_identifier(
        self, fixer, diagnosis_missing_identifier
    ):
        result = fixer.generate_fix_without_ai(diagnosis_missing_identifier)

        add_identifier_actions = [
            a for a in result.actions if a.action_type == "add_identifier"
        ]
        assert len(add_identifier_actions) > 0
        assert any("slack" in a.description.lower() for a in add_identifier_actions)

    def test_generate_fix_without_ai_no_action_needed(
        self, fixer, diagnosis_member_found_with_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_with_activities)

        has_no_action = any(a.action_type == "no_action" for a in result.actions)
        assert has_no_action

    def test_comment_body_contains_member_info(
        self, fixer, diagnosis_member_found_with_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_with_activities)

        assert "Test User" in result.comment_body
        assert "testuser" in result.comment_body
        assert "GitHub" in result.comment_body

    def test_comment_body_contains_identifiers(
        self, fixer, diagnosis_member_found_with_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_with_activities)

        assert "Registered identifiers" in result.comment_body
        assert "github" in result.comment_body.lower()

    def test_comment_body_contains_activity_counts(
        self, fixer, diagnosis_member_found_with_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_with_activities)

        assert "Activity check" in result.comment_body
        assert "10 activities" in result.comment_body

    def test_comment_body_contains_issues_when_present(
        self, fixer, diagnosis_member_found_no_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_no_activities)

        assert "Issues found" in result.comment_body

    def test_comment_body_contains_recommendations_when_present(
        self, fixer, diagnosis_member_found_no_activities
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_no_activities)

        assert "Recommendations" in result.comment_body

    def test_comment_body_contains_suggested_actions(
        self, fixer, diagnosis_member_not_found
    ):
        result = fixer.generate_fix_without_ai(diagnosis_member_not_found)

        assert "Suggested actions" in result.comment_body

    def test_comment_body_footer(self, fixer, diagnosis_member_found_with_activities):
        result = fixer.generate_fix_without_ai(diagnosis_member_found_with_activities)

        assert "generated automatically" in result.comment_body
        assert "issue-automation" in result.comment_body

    def test_fixer_without_api_key_has_no_client(self):
        fixer = AIFixer(api_key=None)
        assert fixer.client is None

    def test_fix_action_dataclass(self):
        action = FixAction(
            action_type="add_identifier",
            description="Add slack identifier",
            script="db.member_identifiers.insertOne(...)",
        )

        assert action.action_type == "add_identifier"
        assert action.description == "Add slack identifier"
        assert action.script is not None

    def test_fix_result_dataclass(self):
        actions = [FixAction(action_type="manual_check", description="Check data")]
        result = FixResult(
            diagnosis_summary="Summary here",
            actions=actions,
            comment_body="Comment body",
        )

        assert result.diagnosis_summary == "Summary here"
        assert len(result.actions) == 1
        assert result.comment_body == "Comment body"


class TestAIFixerWithMockedClient:
    @pytest.fixture
    def mock_anthropic_response(self):
        class MockContent:
            text = '{"summary": "Test summary", "actions": [{"type": "add_identifier", "description": "Add slack ID"}]}'

        class MockResponse:
            content = [MockContent()]

        return MockResponse()

    def test_parse_claude_response_valid_json(self, mock_anthropic_response):
        fixer = AIFixer()
        diagnosis = MockDiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={},
            activities_found={},
            issues=[],
            recommendations=[],
        )

        result = fixer._parse_claude_response(
            mock_anthropic_response.content[0].text, diagnosis
        )

        assert result.diagnosis_summary == "Test summary"
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "add_identifier"

    def test_parse_claude_response_invalid_json_fallback(self):
        fixer = AIFixer()
        diagnosis = MockDiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={"github": ["testuser"]},
            activities_found={"GitHub": 5},
            issues=[],
            recommendations=[],
        )

        result = fixer._parse_claude_response("Not valid JSON at all", diagnosis)

        assert isinstance(result, FixResult)
        assert "Test User" in result.diagnosis_summary

    def test_build_claude_prompt_contains_diagnosis_info(self):
        fixer = AIFixer()
        diagnosis = MockDiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={"github": ["testuser"]},
            activities_found={"GitHub": 10},
            issues=["Test issue"],
            recommendations=["Test recommendation"],
        )

        prompt = fixer._build_claude_prompt(diagnosis)

        assert "All-Thing-Eye" in prompt
        assert "Test User" in prompt
        assert "testuser" in prompt
        assert "member_identifiers" in prompt
