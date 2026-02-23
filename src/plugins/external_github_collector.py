"""External GitHub project data collector for benchmarking.

Collects daily aggregate statistics (commits, PRs, issues) from external
GitHub repositories for comparison with internal Tokamak projects.
"""

import time
import requests
from collections import defaultdict
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta


class ExternalGitHubCollector:
    """Collects daily aggregate stats from external GitHub repositories."""

    GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
    REST_API_BASE = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        })

    def _query_graphql(
        self, query: str, variables: Dict[str, Any], retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Execute GraphQL query with retry logic."""
        for attempt in range(1, retries + 1):
            try:
                response = requests.post(
                    self.GRAPHQL_ENDPOINT,
                    json={"query": query, "variables": variables},
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                if not response.ok:
                    if response.status_code in [502, 503, 504] and attempt < retries:
                        time.sleep(min(2 ** (attempt - 1) * 2, 30))
                        continue
                    raise Exception(
                        f"GitHub API HTTP {response.status_code}: {response.text[:200]}"
                    )
                result = response.json()
                if "errors" in result:
                    print(f"   GraphQL errors: {result['errors']}")
                return result.get("data")
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    time.sleep(min(2 ** (attempt - 1) * 2, 30))
                    continue
                raise
        return None

    def get_repo_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch basic repository information for registration."""
        query = """
            query($owner: String!, $repo: String!) {
                repository(owner: $owner, name: $repo) {
                    name
                    owner { login }
                    description
                    stargazerCount
                    primaryLanguage { name }
                    createdAt
                    isArchived
                }
            }
        """
        result = self._query_graphql(query, {"owner": owner, "repo": repo})
        if not result or not result.get("repository"):
            return None
        r = result["repository"]
        return {
            "owner": r["owner"]["login"],
            "repo": r["name"],
            "full_name": f"{r['owner']['login']}/{r['name']}",
            "description": r.get("description") or "",
            "stars": r.get("stargazerCount", 0),
            "language": r.get("primaryLanguage", {}).get("name") if r.get("primaryLanguage") else None,
            "is_archived": r.get("isArchived", False),
        }

    def collect_daily_stats(
        self, owner: str, repo: str, date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Collect aggregate stats for a single day.

        Args:
            owner: Repository owner (e.g. "paradigmxyz")
            repo: Repository name (e.g. "reth")
            date: The date to collect stats for (date part only used)

        Returns:
            Dict with daily aggregate metrics, or None on failure.
        """
        date_str = date.strftime("%Y-%m-%d")
        since = f"{date_str}T00:00:00Z"
        until = f"{date_str}T23:59:59Z"

        stats = {
            "project_ref": f"{owner}/{repo}",
            "project_type": "external",
            "date": date_str,
            "commits_count": 0,
            "additions": 0,
            "deletions": 0,
            "prs_opened": 0,
            "prs_merged": 0,
            "issues_opened": 0,
            "issues_closed": 0,
            "unique_contributors": 0,
            "collected_at": datetime.now(timezone.utc),
        }

        try:
            # 1. Commits via default branch
            commit_stats = self._collect_commits(owner, repo, since, until)
            stats.update(commit_stats)

            # 2. PRs
            pr_stats = self._collect_prs(owner, repo, date_str)
            stats.update(pr_stats)

            # 3. Issues
            issue_stats = self._collect_issues(owner, repo, date_str)
            stats.update(issue_stats)

            return stats
        except Exception as e:
            print(f"   Error collecting stats for {owner}/{repo} on {date_str}: {e}")
            return None

    def _collect_commits(
        self, owner: str, repo: str, since: str, until: str
    ) -> Dict[str, Any]:
        """Collect commit statistics for the given time range."""
        query = """
            query($owner: String!, $repo: String!, $since: GitTimestamp!, $until: GitTimestamp!) {
                repository(owner: $owner, name: $repo) {
                    defaultBranchRef {
                        target {
                            ... on Commit {
                                history(since: $since, until: $until, first: 100) {
                                    totalCount
                                    nodes {
                                        additions
                                        deletions
                                        author {
                                            user { login }
                                        }
                                    }
                                    pageInfo { hasNextPage endCursor }
                                }
                            }
                        }
                    }
                }
            }
        """
        result = self._query_graphql(
            query, {"owner": owner, "repo": repo, "since": since, "until": until}
        )
        if not result:
            return {}

        repo_data = result.get("repository", {})
        branch_ref = repo_data.get("defaultBranchRef")
        if not branch_ref or not branch_ref.get("target"):
            return {}

        history = branch_ref["target"].get("history", {})
        nodes = history.get("nodes", [])
        total_count = history.get("totalCount", 0)

        additions = sum(n.get("additions", 0) for n in nodes)
        deletions = sum(n.get("deletions", 0) for n in nodes)
        contributors = set()
        for n in nodes:
            user = n.get("author", {}).get("user")
            if user and user.get("login"):
                contributors.add(user["login"])

        # If there are more than 100 commits, paginate
        has_next = history.get("pageInfo", {}).get("hasNextPage", False)
        cursor = history.get("pageInfo", {}).get("endCursor")
        while has_next:
            page_query = """
                query($owner: String!, $repo: String!, $since: GitTimestamp!, $until: GitTimestamp!, $cursor: String!) {
                    repository(owner: $owner, name: $repo) {
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history(since: $since, until: $until, first: 100, after: $cursor) {
                                        nodes {
                                            additions
                                            deletions
                                            author {
                                                user { login }
                                            }
                                        }
                                        pageInfo { hasNextPage endCursor }
                                    }
                                }
                            }
                        }
                    }
                }
            """
            page_result = self._query_graphql(
                page_query,
                {"owner": owner, "repo": repo, "since": since, "until": until, "cursor": cursor},
            )
            if not page_result:
                break
            page_history = (
                page_result.get("repository", {})
                .get("defaultBranchRef", {})
                .get("target", {})
                .get("history", {})
            )
            page_nodes = page_history.get("nodes", [])
            additions += sum(n.get("additions", 0) for n in page_nodes)
            deletions += sum(n.get("deletions", 0) for n in page_nodes)
            for n in page_nodes:
                user = n.get("author", {}).get("user")
                if user and user.get("login"):
                    contributors.add(user["login"])
            has_next = page_history.get("pageInfo", {}).get("hasNextPage", False)
            cursor = page_history.get("pageInfo", {}).get("endCursor")
            time.sleep(0.3)

        return {
            "commits_count": total_count,
            "additions": additions,
            "deletions": deletions,
            "unique_contributors": len(contributors),
        }

    def _collect_prs(self, owner: str, repo: str, date_str: str) -> Dict[str, Any]:
        """Collect PR statistics for the given date."""
        # PRs opened on date
        opened_query = f"repo:{owner}/{repo} is:pr created:{date_str}"
        # PRs merged on date
        merged_query = f"repo:{owner}/{repo} is:pr merged:{date_str}"

        prs_opened = self._search_count(opened_query)
        prs_merged = self._search_count(merged_query)

        return {"prs_opened": prs_opened, "prs_merged": prs_merged}

    def _collect_issues(self, owner: str, repo: str, date_str: str) -> Dict[str, Any]:
        """Collect issue statistics for the given date."""
        # Issues opened on date
        opened_query = f"repo:{owner}/{repo} is:issue created:{date_str}"
        # Issues closed on date
        closed_query = f"repo:{owner}/{repo} is:issue closed:{date_str}"

        issues_opened = self._search_count(opened_query)
        issues_closed = self._search_count(closed_query)

        return {"issues_opened": issues_opened, "issues_closed": issues_closed}

    def _search_count(self, search_query: str) -> int:
        """Use GitHub search API to count results."""
        query = """
            query($q: String!) {
                search(query: $q, type: ISSUE, first: 1) {
                    issueCount
                }
            }
        """
        result = self._query_graphql(query, {"q": search_query})
        if not result:
            return 0
        return result.get("search", {}).get("issueCount", 0)

    # === Bulk range collection (optimized) ===

    def collect_range_stats(
        self, owner: str, repo: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Collect stats for a date range in bulk, grouped by day.

        Instead of N API calls per day, fetches the entire range at once
        and groups by date. ~10-20 API calls total regardless of range.

        Returns:
            List of daily stat dicts ready for DB insertion.
        """
        full_name = f"{owner}/{repo}"
        since = start_date.strftime("%Y-%m-%dT00:00:00Z")
        until = end_date.strftime("%Y-%m-%dT23:59:59Z")
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Initialize per-day buckets
        daily: Dict[str, Dict[str, Any]] = {}
        current = start_date
        while current <= end_date:
            d = current.strftime("%Y-%m-%d")
            daily[d] = {
                "project_ref": full_name,
                "project_type": "external",
                "date": d,
                "commits_count": 0,
                "additions": 0,
                "deletions": 0,
                "prs_opened": 0,
                "prs_merged": 0,
                "issues_opened": 0,
                "issues_closed": 0,
                "unique_contributors": set(),
                "collected_at": datetime.now(timezone.utc),
            }
            current += timedelta(days=1)

        try:
            # 1. Commits - single paginated query for entire range
            self._bulk_collect_commits(owner, repo, since, until, daily)

            # 2. PRs opened
            self._bulk_search_items(
                f"repo:{full_name} is:pr created:{start_str}..{end_str}",
                "createdAt", "prs_opened", daily,
            )
            # 3. PRs merged
            self._bulk_search_items(
                f"repo:{full_name} is:pr merged:{start_str}..{end_str}",
                "closedAt", "prs_merged", daily,
            )
            # 4. Issues opened
            self._bulk_search_items(
                f"repo:{full_name} is:issue created:{start_str}..{end_str}",
                "createdAt", "issues_opened", daily,
            )
            # 5. Issues closed
            self._bulk_search_items(
                f"repo:{full_name} is:issue closed:{start_str}..{end_str}",
                "closedAt", "issues_closed", daily,
            )
        except Exception as e:
            print(f"   Error in bulk collection for {full_name}: {e}")

        # Convert contributor sets to counts
        results = []
        for d in sorted(daily.keys()):
            entry = daily[d]
            entry["unique_contributors"] = len(entry["unique_contributors"])
            results.append(entry)
        return results

    def _bulk_collect_commits(
        self, owner: str, repo: str, since: str, until: str,
        daily: Dict[str, Dict],
    ):
        """Fetch all commits in range and distribute into daily buckets."""
        query = """
            query($owner: String!, $repo: String!, $since: GitTimestamp!, $until: GitTimestamp!, $cursor: String) {
                repository(owner: $owner, name: $repo) {
                    defaultBranchRef {
                        target {
                            ... on Commit {
                                history(since: $since, until: $until, first: 100, after: $cursor) {
                                    nodes {
                                        committedDate
                                        additions
                                        deletions
                                        author { user { login } }
                                    }
                                    pageInfo { hasNextPage endCursor }
                                }
                            }
                        }
                    }
                }
            }
        """
        cursor = None
        has_next = True
        while has_next:
            variables = {"owner": owner, "repo": repo, "since": since, "until": until}
            if cursor:
                variables["cursor"] = cursor

            result = self._query_graphql(query, variables)
            if not result:
                break

            branch = result.get("repository", {}).get("defaultBranchRef")
            if not branch or not branch.get("target"):
                break
            history = branch["target"].get("history", {})
            nodes = history.get("nodes", [])

            for n in nodes:
                committed = n.get("committedDate", "")
                if not committed:
                    continue
                day = committed[:10]  # "2026-02-22"
                if day not in daily:
                    continue
                daily[day]["commits_count"] += 1
                daily[day]["additions"] += n.get("additions", 0)
                daily[day]["deletions"] += n.get("deletions", 0)
                user = n.get("author", {}).get("user")
                if user and user.get("login"):
                    daily[day]["unique_contributors"].add(user["login"])

            has_next = history.get("pageInfo", {}).get("hasNextPage", False)
            cursor = history.get("pageInfo", {}).get("endCursor")
            if has_next:
                time.sleep(0.2)

    def _bulk_search_items(
        self, search_query: str, date_field: str, count_field: str,
        daily: Dict[str, Dict],
    ):
        """Search PRs/Issues in bulk and count per day."""
        query = """
            query($q: String!, $cursor: String) {
                search(query: $q, type: ISSUE, first: 100, after: $cursor) {
                    nodes {
                        ... on PullRequest { createdAt closedAt mergedAt }
                        ... on Issue { createdAt closedAt }
                    }
                    pageInfo { hasNextPage endCursor }
                }
            }
        """
        cursor = None
        has_next = True
        while has_next:
            variables: Dict[str, Any] = {"q": search_query}
            if cursor:
                variables["cursor"] = cursor

            result = self._query_graphql(query, variables)
            if not result:
                break

            search_data = result.get("search", {})
            nodes = search_data.get("nodes", [])

            for n in nodes:
                date_val = n.get(date_field) or n.get("mergedAt") or n.get("closedAt") or n.get("createdAt")
                if not date_val:
                    continue
                day = date_val[:10]
                if day in daily:
                    daily[day][count_field] += 1

            has_next = search_data.get("pageInfo", {}).get("hasNextPage", False)
            cursor = search_data.get("pageInfo", {}).get("endCursor")
            if has_next:
                time.sleep(0.2)

    def collect_internal_repo_daily_stats(
        self, db, repo_name: str, date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Collect daily stats for a single internal repo from existing MongoDB data.

        Args:
            db: Synchronous pymongo database instance
            repo_name: Repository name (e.g. "tokamak-network/reth" or just "reth")
            date: The date to collect stats for

        Returns:
            Dict with daily aggregate metrics, or None on failure.
        """
        date_str = date.strftime("%Y-%m-%d")
        day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
        day_end = datetime(date.year, date.month, date.day, 23, 59, 59)

        try:
            # Commits
            commits = list(db["github_commits"].find({
                "repository": repo_name,
                "date": {"$gte": day_start, "$lte": day_end},
            }))
            additions = sum(c.get("additions", 0) for c in commits)
            deletions = sum(c.get("deletions", 0) for c in commits)
            contributors = set(c.get("author_name", "") for c in commits if c.get("author_name"))

            # PRs
            prs_opened = db["github_pull_requests"].count_documents({
                "repository": repo_name,
                "created_at": {"$gte": day_start, "$lte": day_end},
            })
            prs_merged = db["github_pull_requests"].count_documents({
                "repository": repo_name,
                "merged_at": {"$gte": day_start, "$lte": day_end},
            })

            # Issues
            issues_opened = db["github_issues"].count_documents({
                "repository": repo_name,
                "created_at": {"$gte": day_start, "$lte": day_end},
            })
            issues_closed = db["github_issues"].count_documents({
                "repository": repo_name,
                "closed_at": {"$gte": day_start, "$lte": day_end},
            })

            return {
                "project_ref": f"internal:{repo_name}",
                "project_type": "internal",
                "date": date_str,
                "commits_count": len(commits),
                "additions": additions,
                "deletions": deletions,
                "prs_opened": prs_opened,
                "prs_merged": prs_merged,
                "issues_opened": issues_opened,
                "issues_closed": issues_closed,
                "unique_contributors": len(contributors),
                "collected_at": datetime.now(timezone.utc),
            }
        except Exception as e:
            print(f"   Error collecting internal stats for {repo_name} on {date_str}: {e}")
            return None
