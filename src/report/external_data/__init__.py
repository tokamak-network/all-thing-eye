"""
External Data Fetchers for Report Generation

Provides utilities to fetch external ecosystem data:
- Staking data from The Graph subgraph
- TON/WTON transaction counts from Etherscan
- Market cap data from CoinGecko
"""

from .staking import get_staking_data, get_staking_summary_text
from .transactions import get_ton_wton_tx_counts, get_transactions_summary_text
from .market_cap import get_market_cap_data, get_market_cap_summary_text

__all__ = [
    "get_staking_data",
    "get_staking_summary_text",
    "get_ton_wton_tx_counts",
    "get_transactions_summary_text",
    "get_market_cap_data",
    "get_market_cap_summary_text",
]
