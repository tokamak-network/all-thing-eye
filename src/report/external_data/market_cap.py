"""
Market Cap Data Fetcher

Fetches market cap and price data for TON (TOKAMAK) from MongoDB (preferred)
or CoinGecko API (fallback).
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx

# CoinGecko token ID for Tokamak Network
COINGECKO_TOKEN_ID = "tokamak-network"


async def _get_market_from_mongo(
    mongo_manager,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Fetch market cap data from MongoDB.
    
    Args:
        mongo_manager: MongoDB manager instance
        start_date: Start of period
        end_date: End of period
        
    Returns:
        Dict with market cap data
    """
    db = mongo_manager.async_db
    collection = db["ecosystem_market_cap"]
    
    # Find the most recent record
    cursor = collection.find({}).sort("date", -1).limit(1)
    records = await cursor.to_list(length=1)
    
    if not records:
        raise ValueError("No market cap data found in MongoDB")
    
    record = records[0]
    
    return {
        "market_cap": record.get("market_cap_usd", 0),
        "total_supply": record.get("total_supply", 0),
        "price_high": record.get("price_high_usd", 0),
        "price_low": record.get("price_low_usd", 0),
        "trading_volume": record.get("trading_volume_usd", 0),
        "current_price": record.get("current_price_usd", 0),
        "start_date": record.get("period_start", start_date),
        "end_date": record.get("period_end", end_date)
    }


async def _get_market_from_api(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Fetch market cap data from CoinGecko API.
    
    Args:
        start_date: Start date for price range calculation
        end_date: End date for price range calculation
        
    Returns:
        Dict with market cap data
    """
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=14)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Current market data
        current_url = (
            f"https://api.coingecko.com/api/v3/coins/{COINGECKO_TOKEN_ID}"
            f"?localization=false"
            f"&tickers=false"
            f"&market_data=true"
            f"&community_data=false"
            f"&developer_data=false"
        )
        
        try:
            response = await client.get(current_url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch market data: {e}")
        
        market_data = data.get("market_data", {})
        
        # Historical price data
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        price_url = (
            f"https://api.coingecko.com/api/v3/coins/{COINGECKO_TOKEN_ID}"
            f"/market_chart/range"
            f"?vs_currency=usd"
            f"&from={start_timestamp}"
            f"&to={end_timestamp}"
        )
        
        try:
            price_response = await client.get(price_url)
            price_response.raise_for_status()
            price_data = price_response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch price history: {e}")
        
        # Calculate high/low from price history
        prices = [p[1] for p in price_data.get("prices", [])]
        
        if prices:
            price_high = max(prices)
            price_low = min(prices)
        else:
            current_price = market_data.get("current_price", {}).get("usd", 0)
            price_high = current_price
            price_low = current_price
        
        # Calculate total trading volume over the period
        volumes = price_data.get("total_volumes", [])
        total_volume = sum(v[1] for v in volumes) if volumes else market_data.get("total_volume", {}).get("usd", 0)
        
        return {
            "market_cap": market_data.get("market_cap", {}).get("usd", 0),
            "total_supply": market_data.get("total_supply", 0),
            "price_high": price_high,
            "price_low": price_low,
            "trading_volume": total_volume,
            "current_price": market_data.get("current_price", {}).get("usd", 0),
            "start_date": start_date,
            "end_date": end_date
        }


async def get_market_cap_data(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    mongo_manager = None
) -> Dict[str, Any]:
    """
    Fetch market cap and price data from MongoDB (preferred) or CoinGecko (fallback).
    
    Args:
        start_date: Start date for price range calculation (default: 2 weeks ago)
        end_date: End date for price range calculation (default: now)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Dict containing:
        - market_cap: Current market cap in USD
        - total_supply: Total token supply
        - price_high: Highest price in the period
        - price_low: Lowest price in the period
        - trading_volume: Trading volume in USD
        - current_price: Current price in USD
    """
    # Default to last 2 weeks if not specified
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=14)
    
    # Try MongoDB first
    if mongo_manager is not None:
        try:
            return await _get_market_from_mongo(mongo_manager, start_date, end_date)
        except Exception as e:
            print(f"Warning: Failed to fetch from MongoDB, falling back to API: {e}")
    
    # Fallback to CoinGecko API
    return await _get_market_from_api(start_date, end_date)


def get_market_cap_data_sync(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    mongo_manager = None
) -> Dict[str, Any]:
    """
    Synchronous wrapper for get_market_cap_data.
    
    Args:
        start_date: Start date for price range (optional)
        end_date: End date for price range (optional)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Dict with market cap data
    """
    return asyncio.run(get_market_cap_data(start_date, end_date, mongo_manager))


def _format_number(num: float) -> str:
    """Format number with appropriate suffix (B, M, K)."""
    if num >= 1e9:
        return f"${num / 1e9:.2f}B"
    elif num >= 1e6:
        return f"${num / 1e6:.2f}M"
    elif num >= 1e3:
        return f"${num / 1e3:.2f}K"
    else:
        return f"${num:.2f}"


def _format_supply(num: float) -> str:
    """Format token supply with commas."""
    return f"{num:,.0f}"


def get_market_cap_summary_text(
    market_data: Optional[Dict[str, Any]] = None,
    reference_date: Optional[datetime] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    mongo_manager = None
) -> str:
    """
    Generate a summary text for market cap data.
    
    Args:
        market_data: Pre-fetched market data (optional, will fetch if not provided)
        reference_date: Date to use in the summary (default: end_date or now)
        start_date: Start date for fetching (used if market_data not provided)
        end_date: End date for fetching (used if market_data not provided)
        mongo_manager: MongoDB manager instance (optional)
        
    Returns:
        Formatted summary string for the report
        
    Example output:
        "Tokamak Network recorded a market capitalization of $40.00M with a 
        total issuance of 100,379,236 TON on October 15th. Over the past two weeks, 
        TON token price changed from a high of $1.16 to a low of $0.93, and the 
        total trading volume was $537.34K."
    """
    if market_data is None:
        market_data = get_market_cap_data_sync(start_date, end_date, mongo_manager)
    
    market_cap = market_data.get("market_cap", 0)
    total_supply = market_data.get("total_supply", 0)
    price_high = market_data.get("price_high", 0)
    price_low = market_data.get("price_low", 0)
    trading_volume = market_data.get("trading_volume", 0)
    
    # Format the reference date
    if reference_date:
        date_str = reference_date.strftime("%B %d")
    elif market_data.get("end_date"):
        end_dt = market_data["end_date"]
        if isinstance(end_dt, str):
            end_dt = datetime.strptime(end_dt, "%Y-%m-%d")
        date_str = end_dt.strftime("%B %d")
    else:
        date_str = datetime.now().strftime("%B %d")
    
    return (
        f"Tokamak Network recorded a market capitalization of {_format_number(market_cap)} "
        f"with a total issuance of {_format_supply(total_supply)} TON on {date_str}. "
        f"Over the past two weeks, TON token price changed from a high of ${price_high:.2f} "
        f"to a low of ${price_low:.2f}, and the total trading volume was {_format_number(trading_volume)}. "
        f"For the latest information about total supply and price, please click on "
        f"[Price Dashboard](https://www.tokamak.network/about/price#/)."
    )


# For testing
if __name__ == "__main__":
    import sys
    
    async def main():
        print("Fetching market cap data from API...")
        
        end = datetime.now()
        start = end - timedelta(days=14)
        
        try:
            data = await get_market_cap_data(start, end)
            print(f"Market Cap: {_format_number(data['market_cap'])}")
            print(f"Total Supply: {_format_supply(data['total_supply'])} TON")
            print(f"Price High: ${data['price_high']:.4f}")
            print(f"Price Low: ${data['price_low']:.4f}")
            print(f"Current Price: ${data['current_price']:.4f}")
            print(f"Trading Volume: {_format_number(data['trading_volume'])}")
            print()
            print("Summary text:")
            print(get_market_cap_summary_text(data))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    asyncio.run(main())
