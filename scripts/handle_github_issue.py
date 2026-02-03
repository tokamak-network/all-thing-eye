#!/usr/bin/env python3
"""
GitHub Issue Automation Handler

Automatically diagnoses and proposes fixes for data-not-showing issues.

Usage:
    python scripts/handle_github_issue.py --issue-number 123
    python scripts/handle_github_issue.py --issue-number 123 --dry-run
    python scripts/handle_github_issue.py --all-open
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from scripts.issue_automation.parser import IssueParser, ParsedIssue
from scripts.issue_automation.diagnosis import IssueDiagnoser, DiagnosisResult
from scripts.issue_automation.ai_fixer import AIFixer, FixResult
from scripts.issue_automation.pr_creator import PRCreator


async def handle_issue(issue_number: int, dry_run: bool = False) -> bool:
    print(f"\n{'=' * 60}")
    print(f"Processing Issue #{issue_number}")
    print(f"{'=' * 60}\n")

    parser = IssueParser()
    diagnoser = IssueDiagnoser()
    fixer = AIFixer()
    pr_creator = PRCreator(dry_run=dry_run)

    print("Step 1: Fetching issue...")
    try:
        issue_data = parser.fetch_issue(issue_number)
    except Exception as e:
        print(f"  Error fetching issue: {e}")
        return False

    parsed = parser.parse_issue_body(issue_data.get("body", ""))
    author = parser.get_author_username(issue_data)
    parsed.author_username = author

    print(f"  Author: {author}")
    print(f"  Data sources: {parsed.data_sources}")
    print(f"  Date range: {parsed.date_range}")

    labels = [label.get("name") for label in issue_data.get("labels", [])]
    if "auto-diagnosed" in labels:
        print("  Issue already has 'auto-diagnosed' label. Skipping.")
        return True

    print("\nStep 2: Running diagnosis...")
    try:
        diagnosis = diagnoser.diagnose_by_github_author(
            author,
            sources=parsed.data_sources,
            date_range_str=parsed.date_range,
        )
    except Exception as e:
        print(f"  Error during diagnosis: {e}")
        return False

    print(f"  Member found: {diagnosis.member_found}")
    if diagnosis.member_found:
        print(f"  Member name: {diagnosis.member_name}")
        print(f"  Identifiers: {diagnosis.identifiers}")
        print(f"  Activities: {diagnosis.activities_found}")
    print(f"  Issues: {diagnosis.issues}")

    print("\nStep 3: Generating fix...")
    fix_result = fixer.generate_fix_without_ai(diagnosis)
    print(f"  Summary: {fix_result.diagnosis_summary}")
    print(f"  Actions: {[a.action_type for a in fix_result.actions]}")

    has_actionable_fix = any(
        a.action_type == "add_identifier" and a.script for a in fix_result.actions
    )

    if has_actionable_fix:
        print("\nStep 4: Creating Draft PR...")
        try:
            branch = pr_creator.create_branch(issue_number)

            for action in fix_result.actions:
                if action.script:
                    pr_creator.save_fix_script(issue_number, action.script)

            pr_url = pr_creator.create_draft_pr(
                issue_number=issue_number,
                branch_name=branch,
                title=f"fix: address data issue #{issue_number}",
                body=f"## Auto-generated fix for #{issue_number}\n\n{fix_result.comment_body}",
            )

            if pr_url:
                print(f"  PR created: {pr_url}")
        except Exception as e:
            print(f"  Error creating PR: {e}")
    else:
        print("\nStep 4: No PR needed (no actionable fix)")

    print("\nStep 5: Commenting on issue...")
    pr_creator.add_issue_comment(issue_number, fix_result.comment_body)

    print("\nStep 6: Adding 'auto-diagnosed' label...")
    pr_creator.add_label(issue_number, "auto-diagnosed")

    print(f"\n{'=' * 60}")
    print(f"Issue #{issue_number} processing complete!")
    print(f"{'=' * 60}\n")

    return True


async def main():
    arg_parser = argparse.ArgumentParser(
        description="Automatically diagnose and fix data-not-showing issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/handle_github_issue.py --issue-number 123
  python scripts/handle_github_issue.py --issue-number 123 --dry-run
  python scripts/handle_github_issue.py --all-open
        """,
    )

    arg_parser.add_argument(
        "--issue-number",
        "-n",
        type=int,
        help="Issue number to process",
    )
    arg_parser.add_argument(
        "--all-open",
        action="store_true",
        help="Process all open issues with 'data-issue' label",
    )
    arg_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes (no PR, no comments)",
    )

    args = arg_parser.parse_args()

    if not args.issue_number and not args.all_open:
        arg_parser.print_help()
        sys.exit(1)

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    if args.issue_number:
        success = await handle_issue(args.issue_number, dry_run=args.dry_run)
        sys.exit(0 if success else 1)

    if args.all_open:
        print("--all-open not implemented yet")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
