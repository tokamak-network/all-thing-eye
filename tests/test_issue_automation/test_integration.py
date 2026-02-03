import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestIssueAutomationIntegration:
    @pytest.fixture
    def mock_issue_data(self):
        return {
            "body": """### Which data source is affected?

- [X] GitHub (commits, PRs, issues)
- [ ] Slack (messages)

### What activities are missing?

I made 5 commits to tokamak-network/repo on Jan 28-30

### Date Range

Jan 28 - Feb 3, 2026
""",
            "author": {"login": "testuser"},
            "labels": [{"name": "data-issue"}],
            "title": "[Data Issue] GitHub activities not showing",
        }

    @pytest.fixture
    def mock_diagnosis_result(self):
        from scripts.issue_automation.diagnosis import DiagnosisResult

        return DiagnosisResult(
            member_found=True,
            member_name="Test User",
            github_username="testuser",
            identifiers={"github": ["testuser"]},
            activities_found={"GitHub": 5},
            issues=[],
            recommendations=[],
        )

    def test_parser_to_diagnosis_flow(self, mock_issue_data):
        from scripts.issue_automation.parser import IssueParser

        parser = IssueParser()
        parsed = parser.parse_issue_body(mock_issue_data["body"])
        author = parser.get_author_username(mock_issue_data)

        assert len(parsed.data_sources) > 0
        assert parsed.date_range
        assert author == "testuser"

    def test_diagnosis_to_fixer_flow(self, mock_diagnosis_result):
        from scripts.issue_automation.ai_fixer import AIFixer

        fixer = AIFixer()
        fix_result = fixer.generate_fix_without_ai(mock_diagnosis_result)

        assert fix_result.diagnosis_summary
        assert fix_result.comment_body
        assert "Test User" in fix_result.comment_body

    def test_fixer_to_pr_creator_flow(self, mock_diagnosis_result):
        from scripts.issue_automation.ai_fixer import AIFixer
        from scripts.issue_automation.pr_creator import PRCreator

        fixer = AIFixer()
        fix_result = fixer.generate_fix_without_ai(mock_diagnosis_result)

        pr_creator = PRCreator(dry_run=True)
        result = pr_creator.add_issue_comment(123, fix_result.comment_body)
        assert result == True

    def test_full_pipeline_dry_run(self, mock_issue_data, mock_diagnosis_result):
        from scripts.issue_automation.parser import IssueParser
        from scripts.issue_automation.ai_fixer import AIFixer
        from scripts.issue_automation.pr_creator import PRCreator

        parser = IssueParser()
        parsed = parser.parse_issue_body(mock_issue_data["body"])
        author = parser.get_author_username(mock_issue_data)

        fixer = AIFixer()
        fix_result = fixer.generate_fix_without_ai(mock_diagnosis_result)

        pr_creator = PRCreator(dry_run=True)
        branch = pr_creator.create_branch(123)
        comment_result = pr_creator.add_issue_comment(123, fix_result.comment_body)
        label_result = pr_creator.add_label(123, "auto-diagnosed")

        assert parsed.data_sources == ["GitHub"]
        assert author == "testuser"
        assert "fix/issue-123" in branch
        assert comment_result == True
        assert label_result == True

    def test_all_modules_importable(self):
        from scripts.issue_automation import (
            IssueParser,
            ParsedIssue,
            IssueDiagnoser,
            DiagnosisResult,
            AIFixer,
            FixResult,
            FixAction,
            PRCreator,
        )

        assert IssueParser is not None
        assert ParsedIssue is not None
        assert IssueDiagnoser is not None
        assert DiagnosisResult is not None
        assert AIFixer is not None
        assert FixResult is not None
        assert FixAction is not None
        assert PRCreator is not None
