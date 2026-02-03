import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_issue_body():
    return """### Which data source is affected?

- [X] GitHub (commits, PRs, issues)
- [ ] Slack (messages)
- [X] Notion (page edits)
- [ ] Google Drive (file activities)
- [ ] Meeting Recordings

### What activities are missing?

I made 5 commits to tokamak-network/Tokamak-zk-EVM on Jan 28-30.
Also created 2 PRs that are not showing.

### Date Range

Jan 28 - Feb 3, 2026

### Screenshots (optional)

_No response_
"""


@pytest.fixture
def sample_issue_data(sample_issue_body):
    return {
        "body": sample_issue_body,
        "author": {"login": "testuser"},
        "labels": [{"name": "data-issue"}, {"name": "needs-investigation"}],
        "title": "[Data Issue] GitHub activities not showing",
    }


@pytest.fixture
def mock_subprocess():
    with patch("subprocess.run") as mock_run:
        yield mock_run
