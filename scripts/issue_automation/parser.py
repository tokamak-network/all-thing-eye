import subprocess
import json
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ParsedIssue:
    data_sources: List[str]
    expected_activities: str
    date_range: str
    author_username: str


class IssueParser:
    REPO = "tokamak-network/all-thing-eye"

    def fetch_issue(self, issue_number: int) -> dict:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--repo",
                self.REPO,
                "--json",
                "body,author,labels,title",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def parse_issue_body(self, body: str) -> ParsedIssue:
        # Parse checkboxes for data sources
        data_sources = []
        checkbox_pattern = r"- \[X\] (.+?)(?:\n|$)"
        for match in re.finditer(checkbox_pattern, body, re.IGNORECASE):
            source = match.group(1).strip()
            # Extract just the source name (e.g., "GitHub" from "GitHub (commits, PRs, issues)")
            source_name = source.split("(")[0].strip()
            data_sources.append(source_name)

        # Parse expected activities (textarea after "What activities are missing?")
        expected = ""
        expected_match = re.search(
            r"###\s*What activities are missing\?\s*\n\n(.+?)(?=\n###|\Z)",
            body,
            re.DOTALL | re.IGNORECASE,
        )
        if expected_match:
            expected = expected_match.group(1).strip()

        # Parse date range
        date_range = ""
        date_match = re.search(
            r"###\s*Date Range\s*\n\n(.+?)(?=\n###|\Z)", body, re.DOTALL | re.IGNORECASE
        )
        if date_match:
            date_range = date_match.group(1).strip()

        return ParsedIssue(
            data_sources=data_sources,
            expected_activities=expected,
            date_range=date_range,
            author_username="",  # Set separately via get_author_username
        )

    def get_author_username(self, issue_data: dict) -> str:
        author = issue_data.get("author", {})
        return author.get("login", "")
