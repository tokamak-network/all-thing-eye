#!/usr/bin/env python
"""
Tests for report distribution summary email generation and HTML parsing.

Covers src/report/summary_email.py:
- parse_report_metadata / parse_report_stats (KPI + metadata extraction)
- build_summary_email_html (notification email rendering)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.report.summary_email import (
    build_summary_email_html,
    parse_report_metadata,
    parse_report_stats,
    _format_period,
)


# Minimal report HTML mirroring the real biweekly report structure:
# title with "#N — date", a dark stats bar (font-weight:800 value div + label div),
# and an Executive Summary block.
SAMPLE_HTML = """<!DOCTYPE html><html><head>
<title>Tokamak Network Biweekly Report #8 — May 01-15, 2026</title></head>
<body>
<div style="background-color:#111827;padding:28px 40px;">
  <table>
    <tr>
      <td><div style="font-size:2rem;font-weight:800;color:#fff;">+1,053,543</div><div style="font-size:0.7rem;color:#808080;">Code Changes</div></td>
      <td style="width:1px;background:#333;" width="1"></td>
      <td><div style="font-size:2rem;font-weight:800;color:#2A72E5;">+250,791</div><div style="font-size:0.7rem;">Net Growth</div></td>
      <td style="width:1px;background:#333;" width="1"></td>
      <td><div style="font-size:2rem;font-weight:800;color:#fff;">35</div><div style="font-size:0.7rem;">Active Projects</div></td>
    </tr>
  </table>
</div>
<h2 style="font-size:0.7rem;">Executive Summary</h2>
<h3 style="font-size:1.8rem;">Tokamak Network: 1,053,543 Code Changes</h3>
<p style="font-size:1rem;">Net codebase expansion of +250,791 lines driven by additions.</p>
</body></html>"""


def test_parse_report_stats():
    stats = parse_report_stats(SAMPLE_HTML)
    assert stats == [
        {"value": "+1,053,543", "label": "Code Changes"},
        {"value": "+250,791", "label": "Net Growth"},
        {"value": "35", "label": "Active Projects"},
    ]


def test_parse_report_metadata():
    meta = parse_report_metadata(SAMPLE_HTML)
    assert meta["report_number"] == "8"
    assert meta["date_range"] == "May 01-15, 2026"
    assert meta["title"].startswith("Tokamak Network Biweekly Report #8")
    assert "Net codebase expansion" in meta["executive_summary"]
    assert len(meta["stats"]) == 3


def test_format_period_replaces_first_hyphen_only():
    # Only the first hyphen becomes an em dash (matches JS non-global replace)
    assert _format_period("May 01-15, 2026") == "May 01 — 15, 2026"
    assert _format_period("") == ""


def test_build_summary_email_html():
    meta = parse_report_metadata(SAMPLE_HTML)
    email = build_summary_email_html(
        report_url="https://tokamak-reports.s3.ap-northeast-2.amazonaws.com/r.html",
        stats=meta["stats"],
        summary=meta["executive_summary"],
        report_number=meta["report_number"],
        date_range=meta["date_range"],
    )
    # Core content present
    assert "REPORT #8" in email
    assert "https://tokamak-reports.s3.ap-northeast-2.amazonaws.com/r.html" in email
    assert "+1,053,543" in email
    assert "Active Projects" in email
    # Period formatted with em dash
    assert "May 01 — 15, 2026" in email
    # Two separator cells for three stats
    assert email.count('width="1"') == 2
    # CTA button
    assert "View Full Report" in email


def test_build_summary_email_html_empty_summary_fallback():
    email = build_summary_email_html(
        report_url="https://example.com/r.html",
        stats=[],
        summary="",
        report_number="9",
    )
    assert "The latest biweekly development report is now available." in email
    assert "REPORT #9" in email


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
