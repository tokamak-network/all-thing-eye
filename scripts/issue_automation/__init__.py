"""
Issue Automation Module

Provides tools for automatically handling GitHub issues related to data not showing.
"""

from .parser import IssueParser, ParsedIssue

__all__ = ["IssueParser", "ParsedIssue"]
