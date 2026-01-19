"""
Staking Data Fetcher

Fetches staking data from MongoDB (preferred) or The Graph subgraph (fallback).
Provides total staked TON amount and historical staking data.
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
SUBGRAPH_ID = "CJLiXNdHXJ22BzWignD62gohDRVTYXJQVgU4qKJEtNVS"


def _get_subgraph_endpoint() -> str:
    """Get The Graph API endpoint with API key."""
    api_key = os.getenv("SUBGRAPH_API_KEY", "")
    if not api_key:
        raise ValueError("SUBGRAPH_API_KEY environment variable is required")
    return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{SUBGRAPH_ID}"


def _format_ton(value) -> float:
    """
    Convert staking value to TON.
    
    The Graph staking subgraph stores totalStaked with 27 decimal places,
    not the standard 18 for ERC20 tokens.
    
    Args:
        value: Staking value (string or int) with 27 decimals
        
    Returns:
        Value in TON (float)
    """
    try:
        # Use 10^27 as per github-reporter implementation
        return int(value) / 10**27
    except (ValueError, TypeError):
        return 0.0


async def _get_staking_from_mongo(
    mongo_manager,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Fetch staking data from MongoDB.
    
    Args:
        mongo_manager: MongoDB manager instance
        start_date: Start date for filtering
        end_date: End date for filtering
        
    Returns:
        Dict with staking data
    """
    db = mongo_manager.async_db
    collection = db["ecosystem_staking"]
    
    # Build query
    query = {}
    if start_date or end_date:
        query["date"] = {}
        if start_date:
            query["date"]["$gte"] = start_date
        if end_date:
            query["date"]["$lte"] = end_date
    
    # Fetch data sorted by date
    cursor = collection.find(query).sort("date", 1)
    records = await cursor.to_list(length=None)
    
    if not records:
        raise ValueError("No staking data found in MongoDB")
    
    dates = [r["date"].strftime("%Y-%m-%d") for r in records]
    total_staked = [r.get("total_staked_ton", 0) for r in records]
    
    latest = records[-1]
    
    return {
        "dates": dates,
        "total_staked": total_staked,
        "latest_staked": latest.get("total_staked_ton", 0),
        "latest_date": latest["date"].strftime("%Y-%m-%d")
    }


async def _get_staking_from_api(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    days: int = 91
) -> Dict[str, Any]:
    """
    Fetch staking data from The Graph subgraph API.
    
    Args:
        start_date: Start date for filtering (optional)
        end_date: End date for filtering (optional)
        days: Number of days to fetch (default 91)
        
    Returns:
        Dict with staking data
    """
    endpoint = _get_subgraph_endpoint()
    
    query = """
    query GetStakingData {
        stakingDayDatas(first: %d, orderBy: date, orderDirection: desc) {
            id
            totalStaked
            date
        }
    }
    """ % days
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                json={
                    "operationName": "GetStakingData",
                    "query": query,
                    "variables": {}
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to fetch staking data: {e}")
    
    staking_datas = data.get("data", {}).get("stakingDayDatas", [])
    
    if not staking_datas:
        return {
            "dates": [],
            "total_staked": [],
            "latest_staked": 0,
            "latest_date": None
        }
    
    # Sort by date ascending
    sorted_data = sorted(staking_datas, key=lambda x: x["date"])
    
    # Convert to lists
    dates = [datetime.utcfromtimestamp(int(d["date"])).strftime("%Y-%m-%d") for d in sorted_data]
    values = [d["totalStaked"] for d in sorted_data]
    
    # Convert all values to TON
    total_staked_ton = [_format_ton(v) for v in values]
    
    return {
        "dates": dates,
        "total_staked": total_staked_ton,
        "latest_staked": total_staked_ton[-1] if total_staked_ton else 0,
        "latest_date": dates[-1] if dates else None
    }


async def get_staking_data(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    days: int = 91,
    mongo_manager = None
) -> Dict[str, Any]:
    """
    Fetch staking data from MongoDB (preferred) or The Graph subgraph (fallback).
    
    Args:
        start_date: Start date for filtering (optional)
        end_date: End date for filtering (optional)
        days: Number of days to fetch (default 91 for ~3 months)
        mongo_manager: MongoDB manager instance (optional, will use API if not provided)
        
    Returns:
        Dict containing:
        - dates: List of date strings
        - total_staked: List of staking values in TON
        - latest_staked: Most recent staked amount
        - latest_date: Most recent date
    """
    # Try to fetch from MongoDB first
    if mongo_manager is not None:
        try:
            return await _get_staking_from_mongo(mongo_manager, start_date, end_date)
        except Exception as e:
            print(f"Warning: Failed to fetch from MongoDB, falling back to API: {e}")
    
    # Fallback to The Graph API
    return await _get_staking_from_api(start_date, end_date, days)


def get_staking_data_sync(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    days: int = 91,
    mongo_manager = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for get_staking_data.
    
    Args:
        start_date: Start date for filtering (optional)
        end_date: End date for filtering (optional)
        days: Number of days to fetch (default 91)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Dict with staking data
    """
    return asyncio.run(get_staking_data(start_date, end_date, days, mongo_manager))


def get_staking_summary_text(
    staking_data: Optional[Dict[str, Any]] = None,
    reference_date: Optional[datetime] = None,
    mongo_manager = None
) -> str:
    """
    Generate a summary text for staking data.
    
    Args:
        staking_data: Pre-fetched staking data (optional, will fetch if not provided)
        reference_date: Date to use in the summary (default: latest date from data)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Formatted summary string for the report
        
    Example output:
        "As of January 15th, 2026, the total amount of staked TON (TOKAMAK) 
        has reached 25,939,840 TON."
    """
    if staking_data is None:
        staking_data = get_staking_data_sync(mongo_manager=mongo_manager)
    
    latest_staked = staking_data.get("latest_staked", 0)
    latest_date = staking_data.get("latest_date")
    
    if reference_date:
        date_str = reference_date.strftime("%B %d, %Y")
    elif latest_date:
        if isinstance(latest_date, str):
            date_obj = datetime.strptime(latest_date, "%Y-%m-%d")
        else:
            date_obj = latest_date
        date_str = date_obj.strftime("%B %d, %Y")
    else:
        date_str = datetime.now().strftime("%B %d, %Y")
    
    # Format the staked amount with commas
    formatted_amount = f"{latest_staked:,.0f}"
    
    return f"As of {date_str}, the total amount of staked TON (TOKAMAK) has reached {formatted_amount} TON."


# For testing
if __name__ == "__main__":
    import sys
    
    async def main():
        print("Fetching staking data from API...")
        try:
            data = await get_staking_data()
            print(f"Latest staked: {data['latest_staked']:,.0f} TON")
            print(f"Latest date: {data['latest_date']}")
            print(f"Data points: {len(data['dates'])}")
            print()
            print("Summary text:")
            print(get_staking_summary_text(data))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    asyncio.run(main())
