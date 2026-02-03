import pytest
from unittest.mock import MagicMock
from datetime import datetime

from scripts.issue_automation.diagnosis import IssueDiagnoser, DiagnosisResult


class TestIssueDiagnoser:
    @pytest.fixture
    def mock_collections(self):
        member_identifiers = MagicMock()
        member_identifiers.find_one.return_value = {
            "member_name": "Test User",
            "source": "github",
            "identifier_value": "testuser",
        }
        member_identifiers.find.return_value = [
            {
                "source": "github",
                "identifier_value": "testuser",
                "member_name": "Test User",
            },
            {
                "source": "slack",
                "identifier_value": "U12345",
                "member_name": "Test User",
            },
        ]

        members = MagicMock()
        members.find_one.return_value = None

        github_commits = MagicMock()
        github_commits.count_documents.return_value = 5

        github_pull_requests = MagicMock()
        github_pull_requests.count_documents.return_value = 2

        slack_messages = MagicMock()
        slack_messages.count_documents.return_value = 10

        notion_pages = MagicMock()
        notion_pages.count_documents.return_value = 0

        drive_activities = MagicMock()
        drive_activities.count_documents.return_value = 0

        return {
            "member_identifiers": member_identifiers,
            "members": members,
            "github_commits": github_commits,
            "github_pull_requests": github_pull_requests,
            "slack_messages": slack_messages,
            "notion_pages": notion_pages,
            "drive_activities": drive_activities,
        }

    @pytest.fixture
    def diagnoser_with_db(self, mock_collections):
        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = lambda key: mock_collections.get(
            key, MagicMock()
        )

        d = IssueDiagnoser()
        d._db = mock_db
        return d, mock_collections

    def test_find_member_by_github_username_found(self, diagnoser_with_db):
        diagnoser, mock_collections = diagnoser_with_db
        result = diagnoser.find_member_by_github_username("testuser")
        assert result == "Test User"
        mock_collections["member_identifiers"].find_one.assert_called()

    def test_find_member_by_github_username_not_found(self, diagnoser_with_db):
        diagnoser, mock_collections = diagnoser_with_db
        mock_collections["member_identifiers"].find_one.return_value = None
        mock_collections["members"].find_one.return_value = None

        result = diagnoser.find_member_by_github_username("unknown")
        assert result is None

    def test_find_member_by_github_username_fallback_to_members(
        self, diagnoser_with_db
    ):
        diagnoser, mock_collections = diagnoser_with_db
        mock_collections["member_identifiers"].find_one.return_value = None
        mock_collections["members"].find_one.return_value = {"name": "Member Name"}

        result = diagnoser.find_member_by_github_username("memberuser")
        assert result == "Member Name"

    def test_get_member_identifiers(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        result = diagnoser.get_member_identifiers("Test User")

        assert "github" in result
        assert "testuser" in result["github"]
        assert "slack" in result
        assert "U12345" in result["slack"]

    def test_check_activities_exist_github(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        start_date = datetime(2026, 1, 28)
        end_date = datetime(2026, 2, 3)

        result = diagnoser.check_activities_exist(
            "Test User", ["github"], start_date, end_date
        )

        assert "github" in result
        assert result["github"] == 7

    def test_check_activities_exist_slack(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        start_date = datetime(2026, 1, 28)
        end_date = datetime(2026, 2, 3)

        result = diagnoser.check_activities_exist(
            "Test User", ["slack"], start_date, end_date
        )

        assert "slack" in result
        assert result["slack"] == 10

    def test_check_activities_exist_no_identifiers(self, diagnoser_with_db):
        diagnoser, mock_collections = diagnoser_with_db
        mock_collections["member_identifiers"].find.return_value = []
        start_date = datetime(2026, 1, 28)
        end_date = datetime(2026, 2, 3)

        result = diagnoser.check_activities_exist(
            "Unknown User", ["github", "slack"], start_date, end_date
        )

        assert result["github"] == 0
        assert result["slack"] == 0

    def test_diagnose_member_not_found(self, diagnoser_with_db):
        diagnoser, mock_collections = diagnoser_with_db
        mock_collections["member_identifiers"].find_one.return_value = None
        mock_collections["members"].find_one.return_value = None

        result = diagnoser.diagnose_by_github_author("unknown")

        assert result.member_found is False
        assert result.member_name is None
        assert len(result.issues) > 0
        assert "No member found" in result.issues[0]

    def test_diagnose_member_found_with_activities(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        result = diagnoser.diagnose_by_github_author(
            "testuser", sources=["github", "slack"]
        )

        assert result.member_found is True
        assert result.member_name == "Test User"
        assert result.activities_found["github"] == 7
        assert result.activities_found["slack"] == 10

    def test_diagnose_member_found_missing_source_identifier(self, diagnoser_with_db):
        diagnoser, mock_collections = diagnoser_with_db
        mock_collections["member_identifiers"].find.return_value = [
            {
                "source": "github",
                "identifier_value": "testuser",
                "member_name": "Test User",
            },
        ]

        result = diagnoser.diagnose_by_github_author(
            "testuser", sources=["github", "notion"]
        )

        assert result.member_found is True
        assert "notion" in result.activities_found
        assert result.activities_found["notion"] == 0
        has_notion_issue = any("notion" in issue.lower() for issue in result.issues)
        assert has_notion_issue

    def test_parse_date_range_month_format(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        start, end = diagnoser.parse_date_range("Jan 28 - Feb 3, 2026")

        assert start.year == 2026
        assert start.month == 1
        assert start.day == 28
        assert end.year == 2026
        assert end.month == 2
        assert end.day == 3
        assert end.hour == 23
        assert end.minute == 59

    def test_parse_date_range_iso_format(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        start, end = diagnoser.parse_date_range("2026-01-28 ~ 2026-02-03")

        assert start.year == 2026
        assert start.month == 1
        assert start.day == 28
        assert end.year == 2026
        assert end.month == 2
        assert end.day == 3

    def test_parse_date_range_default(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        start, end = diagnoser.parse_date_range(None)

        assert end.date() == datetime.utcnow().date()
        assert (end - start).days == 30

    def test_format_diagnosis_report(self, diagnoser_with_db):
        diagnoser, _ = diagnoser_with_db
        result = diagnoser.diagnose_by_github_author("testuser", sources=["github"])
        report = diagnoser.format_diagnosis_report(result)

        assert "DIAGNOSIS REPORT" in report
        assert "testuser" in report
        assert "Test User" in report
        assert "IDENTIFIERS:" in report
        assert "ACTIVITY COUNTS:" in report


class TestDiagnosisResult:
    def test_diagnosis_result_dataclass(self):
        result = DiagnosisResult(
            member_found=True,
            member_name="Test",
            github_username="test",
            identifiers={"github": ["test"]},
            activities_found={"github": 5},
            issues=[],
            recommendations=[],
        )

        assert result.member_found is True
        assert result.member_name == "Test"
        assert result.github_username == "test"

    def test_diagnosis_result_defaults(self):
        result = DiagnosisResult(
            member_found=False,
            member_name=None,
            github_username="test",
        )

        assert result.identifiers == {}
        assert result.activities_found == {}
        assert result.issues == []
        assert result.recommendations == []
