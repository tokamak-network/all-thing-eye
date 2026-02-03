import pytest
from scripts.issue_automation.parser import IssueParser, ParsedIssue


class TestIssueParser:
    def test_parse_issue_body_extracts_data_sources(self, sample_issue_body):
        parser = IssueParser()
        result = parser.parse_issue_body(sample_issue_body)
        assert "GitHub" in result.data_sources
        assert "Notion" in result.data_sources
        assert "Slack" not in result.data_sources
        assert len(result.data_sources) == 2

    def test_parse_issue_body_extracts_expected_activities(self, sample_issue_body):
        parser = IssueParser()
        result = parser.parse_issue_body(sample_issue_body)
        assert "5 commits" in result.expected_activities
        assert "2 PRs" in result.expected_activities

    def test_parse_issue_body_extracts_date_range(self, sample_issue_body):
        parser = IssueParser()
        result = parser.parse_issue_body(sample_issue_body)
        assert result.date_range == "Jan 28 - Feb 3, 2026"

    def test_get_author_username(self, sample_issue_data):
        parser = IssueParser()
        username = parser.get_author_username(sample_issue_data)
        assert username == "testuser"

    def test_get_author_username_empty_when_missing(self):
        parser = IssueParser()
        username = parser.get_author_username({})
        assert username == ""

    def test_parse_empty_body(self):
        parser = IssueParser()
        result = parser.parse_issue_body("")
        assert result.data_sources == []
        assert result.expected_activities == ""
        assert result.date_range == ""
