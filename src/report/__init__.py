"""
Report Generation Module for All-Thing-Eye

This module provides AI-powered report generation functionality,
integrating GitHub activity data with external ecosystem data
(staking, transactions, market cap).

Main components:
- external_data: Fetchers for staking, transactions, market cap data
- templates: Report templates
- ai_client: AI API wrapper for Tokamak AI
"""

from .external_data import (
    get_staking_data,
    get_staking_summary_text,
    get_ton_wton_tx_counts,
    get_transactions_summary_text,
    get_market_cap_data,
    get_market_cap_summary_text,
)
from .ai_client import generate_completion, generate_completion_sync

__all__ = [
    "get_staking_data",
    "get_staking_summary_text",
    "get_ton_wton_tx_counts",
    "get_transactions_summary_text",
    "get_market_cap_data",
    "get_market_cap_summary_text",
    "generate_completion",
    "generate_completion_sync",
]
