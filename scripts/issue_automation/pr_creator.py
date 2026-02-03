import subprocess
import os
from datetime import datetime
from typing import Optional


class PRCreator:
    """Creates draft PRs and manages GitHub interactions for issue fixes."""

    REPO = "tokamak-network/all-thing-eye"

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def create_branch(self, issue_number: int) -> str:
        """Create a new branch for the fix."""
        branch_name = f"fix/issue-{issue_number}-data-not-showing"

        if self.dry_run:
            print(f"[DRY RUN] Would create branch: {branch_name}")
            return branch_name

        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)
        subprocess.run(
            ["git", "pull", "origin", "main"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", branch_name], check=True, capture_output=True
        )

        return branch_name

    def save_fix_script(self, issue_number: int, script_content: str) -> str:
        """Save MongoDB fix script to a file."""
        scripts_dir = "scripts/fixes"
        os.makedirs(scripts_dir, exist_ok=True)

        filename = f"{scripts_dir}/fix_issue_{issue_number}.js"

        if self.dry_run:
            print(f"[DRY RUN] Would save script to: {filename}")
            print(f"[DRY RUN] Script content:\n{script_content}")
            return filename

        with open(filename, "w") as f:
            f.write(script_content)

        return filename

    def create_draft_pr(
        self,
        issue_number: int,
        branch_name: str,
        title: str,
        body: str,
    ) -> Optional[str]:
        """Create a draft PR on GitHub."""
        if self.dry_run:
            print(f"[DRY RUN] Would create draft PR:")
            print(f"  Title: {title}")
            print(f"  Branch: {branch_name}")
            print(f"  Body:\n{body[:200]}...")
            return None

        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"fix: address data issue from #{issue_number}"],
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            check=True,
            capture_output=True,
        )

        result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--repo",
                self.REPO,
                "--title",
                title,
                "--body",
                body,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()

    def add_issue_comment(self, issue_number: int, comment_body: str) -> bool:
        """Add a comment to the GitHub issue."""
        if self.dry_run:
            print(f"[DRY RUN] Would comment on issue #{issue_number}:")
            print(f"{comment_body[:300]}...")
            return True

        result = subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(issue_number),
                "--repo",
                self.REPO,
                "--body",
                comment_body,
            ],
            capture_output=True,
            text=True,
        )

        return result.returncode == 0

    def add_label(self, issue_number: int, label: str) -> bool:
        """Add a label to the issue."""
        if self.dry_run:
            print(f"[DRY RUN] Would add label '{label}' to issue #{issue_number}")
            return True

        result = subprocess.run(
            [
                "gh",
                "issue",
                "edit",
                str(issue_number),
                "--repo",
                self.REPO,
                "--add-label",
                label,
            ],
            capture_output=True,
            text=True,
        )

        return result.returncode == 0
