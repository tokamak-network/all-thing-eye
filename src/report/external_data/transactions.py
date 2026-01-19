"""
TON/WTON Transaction Counter

Fetches TON and WTON token transaction counts from MongoDB (preferred) 
or Etherscan API (fallback).
"""

import os
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Contract addresses
TON_CONTRACT = "0x2be5e8c109e2197D077D13A82dAead6a9b3433C5"
WTON_CONTRACT = "0xc4a11aaf6ea915ed7ac194161d2fc9384f15bff2"

# Cache for block numbers
_block_number_cache: Dict[int, str] = {}


def _get_etherscan_api_key() -> str:
    """Get Etherscan API key from environment."""
    api_key = os.getenv("ETHERSCAN_API_KEY", "")
    if not api_key:
        raise ValueError("ETHERSCAN_API_KEY environment variable is required")
    return api_key


async def _get_tx_from_mongo(
    mongo_manager,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Fetch transaction data from MongoDB.
    
    Args:
        mongo_manager: MongoDB manager instance
        start_date: Start of period
        end_date: End of period
        
    Returns:
        Dict with transaction counts
    """
    db = mongo_manager.async_db
    collection = db["ecosystem_transactions"]
    
    # Find record matching the date range (or closest match)
    date_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, datetime) else str(end_date)
    
    # Try exact match first
    record = await collection.find_one({"date": date_str})
    
    if not record:
        # Try to find the most recent record within range
        cursor = collection.find({}).sort("date", -1).limit(1)
        records = await cursor.to_list(length=1)
        if records:
            record = records[0]
    
    if not record:
        raise ValueError("No transaction data found in MongoDB")
    
    return {
        "ton_count": record.get("ton_count", 0),
        "wton_count": record.get("wton_count", 0),
        "start_date": record.get("period_start", start_date),
        "end_date": record.get("period_end", end_date)
    }


async def _delay(ms: int) -> None:
    """Async delay in milliseconds."""
    await asyncio.sleep(ms / 1000)


async def _get_block_number(timestamp: int, client: httpx.AsyncClient) -> str:
    """Get Ethereum block number for a given Unix timestamp."""
    if timestamp in _block_number_cache:
        return _block_number_cache[timestamp]
    
    api_key = _get_etherscan_api_key()
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            await _delay(250 + random.randint(0, 100))
            
            url = (
                f"https://api.etherscan.io/api"
                f"?module=block"
                f"&action=getblocknobytime"
                f"&timestamp={timestamp}"
                f"&closest=before"
                f"&apikey={api_key}"
            )
            
            response = await client.get(url)
            data = response.json()
            
            if data.get("status") == "1" and data.get("result"):
                block_number = data["result"]
                _block_number_cache[timestamp] = block_number
                return block_number
            else:
                error_msg = data.get("message", "Unknown error")
                if "Max rate limit reached" in error_msg:
                    await _delay(1000 * (attempt + 1))
                    continue
                raise RuntimeError(f"Etherscan API error: {error_msg}")
                
        except httpx.HTTPError as e:
            if attempt < max_attempts - 1:
                await _delay(1000 * (attempt + 1))
                continue
            raise RuntimeError(f"Failed to get block number: {e}")
    
    raise RuntimeError("Failed to get block number after multiple attempts")


async def _get_token_tx_count(
    contract: str,
    start_time: int,
    end_time: int,
    client: httpx.AsyncClient
) -> int:
    """Get token transaction count for a contract within a time range."""
    api_key = _get_etherscan_api_key()
    
    start_block = await _get_block_number(start_time, client)
    end_block = await _get_block_number(end_time, client)
    
    all_transactions = []
    page = 1
    max_attempts = 5
    
    while True:
        for attempt in range(max_attempts):
            try:
                await _delay(300)
                
                url = (
                    f"https://api.etherscan.io/api"
                    f"?module=account"
                    f"&action=tokentx"
                    f"&contractaddress={contract}"
                    f"&startblock={start_block}"
                    f"&endblock={end_block}"
                    f"&page={page}"
                    f"&offset=1000"
                    f"&sort=asc"
                    f"&apikey={api_key}"
                )
                
                response = await client.get(url)
                data = response.json()
                
                if data.get("status") == "1" and data.get("result"):
                    results = data["result"]
                    if not results:
                        break
                    all_transactions.extend(results)
                    if len(results) < 1000:
                        break
                    page += 1
                    break
                elif data.get("message") == "No transactions found":
                    break
                else:
                    error_msg = data.get("message", "Unknown error")
                    if "Max rate limit reached" in error_msg:
                        await _delay(1000 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Etherscan API error: {error_msg}")
                    
            except httpx.HTTPError as e:
                if attempt < max_attempts - 1:
                    await _delay(1000 * (attempt + 1))
                    continue
                raise RuntimeError(f"Failed to get transactions: {e}")
        else:
            break
        
        if data.get("status") != "1" or len(data.get("result", [])) < 1000:
            break
    
    # Filter by timestamp
    filtered_transactions = [
        tx for tx in all_transactions
        if start_time <= int(tx.get("timeStamp", 0)) <= end_time
    ]
    
    return len(filtered_transactions)


async def _get_tx_from_api(
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Fetch transaction counts from Etherscan API.
    
    Args:
        start_date: Start of period
        end_date: End of period
        
    Returns:
        Dict with transaction counts
    """
    start_time = int(start_date.timestamp())
    end_time = int(end_date.timestamp())
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        ton_count = await _get_token_tx_count(TON_CONTRACT, start_time, end_time, client)
        wton_count = await _get_token_tx_count(WTON_CONTRACT, start_time, end_time, client)
    
    return {
        "ton_count": ton_count,
        "wton_count": wton_count,
        "start_date": start_date,
        "end_date": end_date
    }


async def get_ton_wton_tx_counts(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    mongo_manager = None
) -> Dict[str, Any]:
    """
    Get TON and WTON transaction counts from MongoDB (preferred) or Etherscan (fallback).
    
    Args:
        start_date: Start date (default: 2 weeks ago)
        end_date: End date (default: now)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Dict containing:
        - ton_count: Number of TON transactions
        - wton_count: Number of WTON transactions
        - start_date: Start date used
        - end_date: End date used
    """
    # Default to last 2 weeks if not specified
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=14)
    
    # Try MongoDB first
    if mongo_manager is not None:
        try:
            return await _get_tx_from_mongo(mongo_manager, start_date, end_date)
        except Exception as e:
            print(f"Warning: Failed to fetch from MongoDB, falling back to API: {e}")
    
    # Fallback to Etherscan API
    return await _get_tx_from_api(start_date, end_date)


def get_ton_wton_tx_counts_sync(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    mongo_manager = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for get_ton_wton_tx_counts.
    
    Args:
        start_date: Start date (optional)
        end_date: End date (optional)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Dict with transaction counts
    """
    return asyncio.run(get_ton_wton_tx_counts(start_date, end_date, mongo_manager))


def get_transactions_summary_text(
    tx_data: Optional[Dict[str, Any]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    mongo_manager = None
) -> str:
    """
    Generate a summary text for transaction data.
    
    Args:
        tx_data: Pre-fetched transaction data (optional, will fetch if not provided)
        start_date: Start date (used if tx_data not provided)
        end_date: End date (used if tx_data not provided)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Formatted summary string for the report
        
    Example output:
        "In the past two weeks, Tokamak Network has recorded 408 TON 
        transactions and 611 WTON transactions."
    """
    if tx_data is None:
        tx_data = get_ton_wton_tx_counts_sync(start_date, end_date, mongo_manager)
    
    ton_count = tx_data.get("ton_count", 0)
    wton_count = tx_data.get("wton_count", 0)
    
    return (
        f"In the past two weeks, Tokamak Network has recorded "
        f"{ton_count} TON transactions and {wton_count} WTON transactions."
    )


# For testing
if __name__ == "__main__":
    import sys
    
    async def main():
        print("Fetching TON/WTON transaction counts from API...")
        
        end = datetime.now()
        start = end - timedelta(days=14)
        
        try:
            data = await get_ton_wton_tx_counts(start, end)
            print(f"TON transactions: {data['ton_count']}")
            print(f"WTON transactions: {data['wton_count']}")
            print(f"Period: {data['start_date']} to {data['end_date']}")
            print()
            print("Summary text:")
            print(get_transactions_summary_text(data))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    asyncio.run(main())
