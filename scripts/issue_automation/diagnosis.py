"""
Diagnosis Module for Issue Automation

Provides diagnostic capabilities to identify why member data might not be showing
in reports. Queries MongoDB to check member identifiers and activity data.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import re

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()


@dataclass
class DiagnosisResult:
    """Result of diagnosing a member's data visibility issues."""

    member_found: bool
    member_name: Optional[str]
    github_username: str
    identifiers: Dict[str, List[str]] = field(default_factory=dict)
    activities_found: Dict[str, int] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class IssueDiagnoser:
    """
    Diagnoses data visibility issues for members.

    Connects to MongoDB to check:
    - If member exists in member_identifiers
    - What identifiers are registered for the member
    - If activities exist in each data source for the given date range
    """

    def __init__(self):
        self._db = None
        self._mongo_manager = None

    def _ensure_connection(self):
        """Ensure MongoDB connection is established (synchronous)."""
        if self._db is None:
            from src.core.mongo_manager import get_mongo_manager
            from src.core.config import get_config

            config = get_config()
            mongo_config = config.get("database", {}).get("mongodb", {})
            self._mongo_manager = get_mongo_manager(mongo_config)
            self._db = self._mongo_manager.db

    @property
    def db(self):
        """Get database instance, establishing connection if needed."""
        self._ensure_connection()
        return self._db

    def find_member_by_github_username(self, github_username: str) -> Optional[str]:
        """
        Find member name by GitHub username in member_identifiers.

        Args:
            github_username: GitHub username to search for

        Returns:
            Member name if found, None otherwise
        """
        identifier = self.db["member_identifiers"].find_one(
            {
                "source": "github",
                "identifier_value": {
                    "$regex": f"^{re.escape(github_username)}$",
                    "$options": "i",
                },
            }
        )

        if identifier:
            return identifier.get("member_name")

        member = self.db["members"].find_one(
            {
                "github_username": {
                    "$regex": f"^{re.escape(github_username)}$",
                    "$options": "i",
                }
            }
        )
        if member:
            return member.get("name")

        return None

    def get_member_identifiers(self, member_name: str) -> Dict[str, List[str]]:
        """
        Get all identifiers for a member across different sources.

        Args:
            member_name: Name of the member

        Returns:
            Dict mapping source type to list of identifier values
            Example: {'github': ['testuser'], 'slack': ['U12345']}
        """
        identifiers: Dict[str, List[str]] = {}

        cursor = self.db["member_identifiers"].find(
            {"member_name": {"$regex": f"^{re.escape(member_name)}$", "$options": "i"}}
        )

        for doc in cursor:
            source = doc.get("source")
            value = doc.get("identifier_value")
            if source and value:
                if source not in identifiers:
                    identifiers[source] = []
                identifiers[source].append(value)

        return identifiers

    def check_activities_exist(
        self,
        member_name: str,
        sources: List[str],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, int]:
        """
        Check if activities exist for member in given sources and date range.

        Args:
            member_name: Name of the member
            sources: List of source types to check (github, slack, notion, drive)
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict mapping source to activity count
        """
        identifiers = self.get_member_identifiers(member_name)

        counts: Dict[str, int] = {}

        for source in sources:
            source_lower = source.lower()
            count = 0

            if source_lower == "github":
                github_usernames = identifiers.get("github", [])
                if github_usernames:
                    count = self.db["github_commits"].count_documents(
                        {
                            "$or": [
                                {"author_name": {"$in": github_usernames}},
                                {"author_login": {"$in": github_usernames}},
                                {"author": {"$in": github_usernames}},
                            ],
                            "date": {"$gte": start_date, "$lte": end_date},
                        }
                    )

                    pr_count = self.db["github_pull_requests"].count_documents(
                        {
                            "author": {"$in": github_usernames},
                            "created_at": {"$gte": start_date, "$lte": end_date},
                        }
                    )
                    count += pr_count

            elif source_lower == "slack":
                slack_ids = identifiers.get("slack", [])
                if slack_ids:
                    count = self.db["slack_messages"].count_documents(
                        {
                            "user_id": {"$in": slack_ids},
                            "posted_at": {"$gte": start_date, "$lte": end_date},
                        }
                    )

            elif source_lower == "notion":
                notion_ids = identifiers.get("notion", [])
                if notion_ids:
                    count = self.db["notion_pages"].count_documents(
                        {
                            "$or": [
                                {"created_by.id": {"$in": notion_ids}},
                                {"last_edited_by.id": {"$in": notion_ids}},
                            ],
                            "created_time": {"$gte": start_date, "$lte": end_date},
                        }
                    )

            elif source_lower == "drive":
                drive_emails = identifiers.get("drive", []) + identifiers.get(
                    "email", []
                )
                if drive_emails:
                    count = self.db["drive_activities"].count_documents(
                        {
                            "actor_email": {"$in": drive_emails},
                            "time": {"$gte": start_date, "$lte": end_date},
                        }
                    )

            counts[source] = count

        return counts

    def parse_date_range(
        self, date_range_str: Optional[str]
    ) -> tuple[datetime, datetime]:
        """
        Parse date range string into start and end datetime.

        Supports formats like:
        - "Jan 28 - Feb 3, 2026"
        - "2026-01-28 ~ 2026-02-03"

        Args:
            date_range_str: Date range string to parse

        Returns:
            Tuple of (start_date, end_date)
        """
        if not date_range_str:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            return start_date, end_date

        pattern1 = r"([A-Za-z]+)\s+(\d+)\s*-\s*([A-Za-z]+)\s+(\d+),?\s*(\d{4})"
        match = re.match(pattern1, date_range_str.strip())
        if match:
            start_month, start_day, end_month, end_day, year = match.groups()
            try:
                start_date = datetime.strptime(
                    f"{start_month} {start_day} {year}", "%b %d %Y"
                )
                end_date = datetime.strptime(
                    f"{end_month} {end_day} {year}", "%b %d %Y"
                )
                end_date = end_date.replace(hour=23, minute=59, second=59)
                return start_date, end_date
            except ValueError:
                pass

        pattern2 = r"(\d{4}-\d{2}-\d{2})\s*[~-]\s*(\d{4}-\d{2}-\d{2})"
        match = re.match(pattern2, date_range_str.strip())
        if match:
            start_str, end_str = match.groups()
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                end_date = datetime.strptime(end_str, "%Y-%m-%d")
                end_date = end_date.replace(hour=23, minute=59, second=59)
                return start_date, end_date
            except ValueError:
                pass

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date

    def diagnose_by_github_author(
        self,
        github_username: str,
        sources: Optional[List[str]] = None,
        date_range_str: Optional[str] = None,
    ) -> DiagnosisResult:
        """
        Main diagnosis method - identifies why a member's data might not be showing.

        Args:
            github_username: GitHub username to diagnose
            sources: List of sources to check (default: all common sources)
            date_range_str: Date range string (e.g., "Jan 28 - Feb 3, 2026")

        Returns:
            DiagnosisResult with findings and recommendations
        """
        issues: List[str] = []
        recommendations: List[str] = []

        if sources is None:
            sources = ["github", "slack", "notion", "drive"]

        member_name = self.find_member_by_github_username(github_username)

        if not member_name:
            issues.append(f"No member found with GitHub username '{github_username}'")
            recommendations.append(
                f"Add GitHub identifier for '{github_username}' in member_identifiers collection:\n"
                f"  db.member_identifiers.insertOne({{\n"
                f"    member_name: '<actual_member_name>',\n"
                f"    source: 'github',\n"
                f"    identifier_value: '{github_username}'\n"
                f"  }})"
            )
            return DiagnosisResult(
                member_found=False,
                member_name=None,
                github_username=github_username,
                identifiers={},
                activities_found={},
                issues=issues,
                recommendations=recommendations,
            )

        identifiers = self.get_member_identifiers(member_name)
        start_date, end_date = self.parse_date_range(date_range_str)
        activities_found = self.check_activities_exist(
            member_name, sources, start_date, end_date
        )

        for source in sources:
            source_lower = source.lower()
            count = activities_found.get(source, 0)

            if count == 0:
                source_identifiers = identifiers.get(source_lower, [])

                if not source_identifiers:
                    issues.append(
                        f"No {source} identifier found for member '{member_name}'"
                    )
                    recommendations.append(
                        f"Add {source} identifier to member_identifiers:\n"
                        f"  db.member_identifiers.insertOne({{\n"
                        f"    member_name: '{member_name}',\n"
                        f"    source: '{source_lower}',\n"
                        f"    identifier_value: '<{source_lower}_id>'\n"
                        f"  }})"
                    )
                else:
                    issues.append(
                        f"No {source} activities found for '{member_name}' in date range "
                        f"({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})"
                    )
                    recommendations.append(
                        f"Verify {source} data collection is working. Check if:\n"
                        f"  1. Data collection script ran successfully\n"
                        f"  2. The {source} identifier '{source_identifiers[0]}' is correct\n"
                        f"  3. The member had actual activity in this date range"
                    )

        return DiagnosisResult(
            member_found=True,
            member_name=member_name,
            github_username=github_username,
            identifiers=identifiers,
            activities_found=activities_found,
            issues=issues,
            recommendations=recommendations,
        )

    def format_diagnosis_report(self, result: DiagnosisResult) -> str:
        """
        Format diagnosis result as a human-readable report.

        Args:
            result: DiagnosisResult to format

        Returns:
            Formatted string report
        """
        lines = [
            "=" * 60,
            "DIAGNOSIS REPORT",
            "=" * 60,
            f"GitHub Username: {result.github_username}",
            f"Member Found: {'Yes' if result.member_found else 'No'}",
        ]

        if result.member_name:
            lines.append(f"Member Name: {result.member_name}")

        lines.append("")
        lines.append("IDENTIFIERS:")
        if result.identifiers:
            for source, values in result.identifiers.items():
                lines.append(f"  {source}: {', '.join(values)}")
        else:
            lines.append("  (none found)")

        lines.append("")
        lines.append("ACTIVITY COUNTS:")
        if result.activities_found:
            for source, count in result.activities_found.items():
                status = "✓" if count > 0 else "✗"
                lines.append(f"  {status} {source}: {count}")
        else:
            lines.append("  (not checked)")

        if result.issues:
            lines.append("")
            lines.append("ISSUES FOUND:")
            for i, issue in enumerate(result.issues, 1):
                lines.append(f"  {i}. {issue}")

        if result.recommendations:
            lines.append("")
            lines.append("RECOMMENDATIONS:")
            for i, rec in enumerate(result.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        lines.append("=" * 60)
        return "\n".join(lines)
