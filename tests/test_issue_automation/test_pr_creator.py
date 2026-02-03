import pytest
from unittest.mock import MagicMock, patch
from scripts.issue_automation.pr_creator import PRCreator


class TestPRCreator:
    def test_create_branch_dry_run(self, capsys):
        creator = PRCreator(dry_run=True)
        branch = creator.create_branch(123)
        assert branch == "fix/issue-123-data-not-showing"

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "fix/issue-123" in captured.out

    def test_save_fix_script_dry_run(self, capsys):
        creator = PRCreator(dry_run=True)
        script = "db.collection.insertOne({test: 1})"
        filename = creator.save_fix_script(123, script)

        assert "fix_issue_123" in filename

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "insertOne" in captured.out

    def test_add_issue_comment_dry_run(self, capsys):
        creator = PRCreator(dry_run=True)
        result = creator.add_issue_comment(123, "Test comment body")

        assert result is True

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "comment" in captured.out.lower()

    def test_add_label_dry_run(self, capsys):
        creator = PRCreator(dry_run=True)
        result = creator.add_label(123, "auto-diagnosed")

        assert result is True

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "auto-diagnosed" in captured.out

    def test_create_draft_pr_dry_run(self, capsys):
        creator = PRCreator(dry_run=True)
        pr_url = creator.create_draft_pr(
            issue_number=123,
            branch_name="fix/issue-123-data-not-showing",
            title="fix: address data issue #123",
            body="## Auto-generated fix\n\nThis is a test PR body.",
        )

        assert pr_url is None

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "fix: address data issue #123" in captured.out

    @patch("scripts.issue_automation.pr_creator.subprocess.run")
    def test_create_branch_real(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        creator = PRCreator(dry_run=False)

        branch = creator.create_branch(456)

        assert branch == "fix/issue-456-data-not-showing"
        assert mock_run.call_count == 3

    @patch("scripts.issue_automation.pr_creator.subprocess.run")
    def test_add_label_real_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        creator = PRCreator(dry_run=False)

        result = creator.add_label(123, "bug")

        assert result is True
        mock_run.assert_called_once()

    @patch("scripts.issue_automation.pr_creator.subprocess.run")
    def test_add_label_real_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        creator = PRCreator(dry_run=False)

        result = creator.add_label(123, "bug")

        assert result is False

    @patch("scripts.issue_automation.pr_creator.subprocess.run")
    def test_add_issue_comment_real_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        creator = PRCreator(dry_run=False)

        result = creator.add_issue_comment(123, "This is a test comment")

        assert result is True

    @patch("scripts.issue_automation.pr_creator.subprocess.run")
    def test_add_issue_comment_real_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        creator = PRCreator(dry_run=False)

        result = creator.add_issue_comment(123, "This is a test comment")

        assert result is False
