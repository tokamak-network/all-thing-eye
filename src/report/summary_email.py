"""
Summary email generation for biweekly report distribution.

Builds the notification email that links to the full report on S3, and parses
KPI stats / metadata out of an uploaded report HTML.

Ported from biweekly-reporter:
- client/src/App.tsx `generateEmailHtml()` / `extractMetadataFromHtml()`
- server/index.ts KPI extraction regex
"""

import re
from typing import Optional, TypedDict


class ReportStat(TypedDict):
    value: str
    label: str


class ReportMetadata(TypedDict):
    title: str
    report_number: str
    date_range: str
    executive_summary: str
    stats: list[ReportStat]


# <div ...font-weight:800...>VALUE</div> <div ...>LABEL</div>  (the dark stats bar)
_KPI_RE = re.compile(
    r"font-weight:800[^>]*>([^<]+)</div>\s*<div[^>]*>([^<]+)</div>",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
_NUM_RE = re.compile(r"#(\d+)")
_DATE_RE = re.compile(r"—\s*(.+)$")
_SUMMARY_RE = re.compile(
    r"Executive Summary</h2>\s*<h3[^>]*>[^<]*</h3>\s*<p[^>]*>(.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)


def parse_report_stats(html: str) -> list[ReportStat]:
    """Extract raw (value, label) KPI pairs from the report's dark stats bar."""
    return [
        {"value": value.strip(), "label": label.strip()}
        for value, label in _KPI_RE.findall(html)
    ]


def parse_report_metadata(html: str) -> ReportMetadata:
    """
    Extract title, report number, date range, executive summary, and KPI stats
    from an uploaded report HTML. Mirrors App.tsx `extractMetadataFromHtml`.
    """
    title = ""
    report_number = ""
    date_range = ""

    title_match = _TITLE_RE.search(html)
    if title_match:
        title = title_match.group(1).strip()
        num_match = _NUM_RE.search(title)
        if num_match:
            report_number = num_match.group(1)
        date_match = _DATE_RE.search(title)
        if date_match:
            date_range = date_match.group(1).strip()

    executive_summary = ""
    summary_match = _SUMMARY_RE.search(html)
    if summary_match:
        executive_summary = summary_match.group(1).strip()

    return {
        "title": title,
        "report_number": report_number,
        "date_range": date_range,
        "executive_summary": executive_summary,
        "stats": parse_report_stats(html),
    }


def _format_period(date_range: str) -> str:
    """Replace only the FIRST hyphen with an em dash (matches JS non-global replace)."""
    if not date_range:
        return ""
    return date_range.replace("-", " — ", 1)


def _build_stats_cells(stats: list[ReportStat]) -> str:
    cells = []
    for i, s in enumerate(stats):
        separator = (
            '<td style="width:1px;background:#333333;" width="1"></td>' if i > 0 else ""
        )
        cells.append(
            f"""{separator}
        <td style="text-align:center;padding:20px 8px;">
          <div style="font-size:1.8rem;font-weight:800;color:#ffffff;">{s['value']}</div>
          <div style="font-size:0.65rem;color:#808080;text-transform:uppercase;letter-spacing:2px;margin-top:4px;">{s['label']}</div>
        </td>"""
        )
    return "".join(cells)


def build_summary_email_html(
    report_url: str,
    stats: list[ReportStat],
    summary: str,
    report_number: str,
    date_range: str = "",
) -> str:
    """
    Build the HTML summary/notification email.

    Faithful port of App.tsx `generateEmailHtml()` — inline-styled, table-based
    layout (hero header / stats bar / executive summary + CTA / footer).
    """
    formatted_period = _format_period(date_range)
    stats_cells = _build_stats_cells(stats)
    summary_text = summary or "The latest biweekly development report is now available."

    period_hero = (
        f'<p style="font-size:1.3rem;color:#d9d9d9;font-weight:500;margin:24px 0 0;">{formatted_period}</p>'
        if formatted_period
        else ""
    )
    period_footer = f" &middot; {formatted_period}" if formatted_period else ""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1a1a1a;background:#f8f9fa;">

<!-- HERO HEADER -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#111827;">
  <tr><td style="padding:60px 40px 24px;text-align:center;">
    <div style="font-size:1rem;color:#2A72E5;letter-spacing:6px;text-transform:uppercase;font-weight:600;margin-bottom:24px;">TOKAMAK NETWORK</div>
    <h1 style="font-size:2.8rem;font-weight:800;color:#ffffff;letter-spacing:-1px;line-height:1.1;margin:0 0 16px;">BIWEEKLY<br>REPORT #{report_number}</h1>
    <div style="width:60px;height:3px;background:#2A72E5;margin:24px auto;"></div>
    <p style="font-size:1.1rem;color:#999999;font-weight:300;letter-spacing:4px;text-transform:uppercase;margin:0;">Bi-Weekly Engineering Update</p>
    {period_hero}
  </td></tr>
</table>

<!-- STATS BAR -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#111827;">
  <tr><td style="padding:0 40px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:700px;margin:0 auto;border-top:1px solid #333333;">
      <tr>{stats_cells}</tr>
    </table>
  </td></tr>
</table>

<!-- EXECUTIVE SUMMARY -->
<table width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr><td style="padding:48px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:700px;margin:0 auto;">
      <tr><td>
        <h2 style="font-size:0.7rem;font-weight:600;color:#2A72E5;text-transform:uppercase;letter-spacing:3px;margin:0 0 16px;">Executive Summary</h2>
        <p style="font-size:1rem;color:#444444;line-height:1.8;margin:0 0 40px;">{summary_text}</p>

        <table cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">
          <tr><td style="border-radius:8px;background:#2A72E5;text-align:center;">
            <a href="{report_url}" target="_blank" style="display:inline-block;padding:16px 48px;color:#ffffff;font-size:1rem;font-weight:600;text-decoration:none;letter-spacing:0.5px;">View Full Report</a>
          </td></tr>
        </table>

        <p style="font-size:0.8rem;color:#999999;text-align:center;margin-top:16px;">
          Click the button above to read the complete report with detailed repository breakdowns, ecosystem landscape, and architecture blueprint.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>

<!-- FOOTER -->
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#111827;">
  <tr><td style="padding:40px;text-align:center;">
    <div style="font-size:1rem;color:#2A72E5;letter-spacing:4px;text-transform:uppercase;font-weight:600;margin-bottom:12px;">TOKAMAK NETWORK</div>
    <p style="color:#888888;font-size:0.8rem;margin:0;">Biweekly Report #{report_number}{period_footer}</p>
    <p style="color:#aaaaaa;font-size:0.7rem;margin:4px 0 0;">Generated automatically from GitHub activity data</p>
  </td></tr>
</table>

</body>
</html>"""
