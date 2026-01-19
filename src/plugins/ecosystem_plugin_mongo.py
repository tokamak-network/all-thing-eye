"""
Ecosystem Data Plugin for MongoDB

Collects and stores external ecosystem data:
- Staking data from The Graph subgraph
- TON/WTON transaction counts from Etherscan
- Market cap data from CoinGecko

This plugin follows the same pattern as other data source plugins.
"""

import os
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import httpx
from dotenv import load_dotenv

from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# Constants
SUBGRAPH_ID = "CJLiXNdHXJ22BzWignD62gohDRVTYXJQVgU4qKJEtNVS"
TON_CONTRACT = "0x2be5e8c109e2197D077D13A82dAead6a9b3433C5"
WTON_CONTRACT = "0xc4a11aaf6ea915ed7ac194161d2fc9384f15bff2"
COINGECKO_TOKEN_ID = "tokamak-network"


class EcosystemPluginMongo:
    """
    Plugin for collecting ecosystem data (staking, transactions, market cap).
    """
    
    def __init__(self, config: Dict[str, Any], mongo_manager):
        """
        Initialize the ecosystem plugin.
        
        Args:
            config: Plugin configuration dict
            mongo_manager: MongoDBManager instance
        """
        self.config = config
        self.mongo_manager = mongo_manager
        self.enabled = config.get('enabled', True)
        
        # API keys from config or environment
        self.subgraph_api_key = config.get('subgraph_api_key') or os.getenv('SUBGRAPH_API_KEY', '')
        self.etherscan_api_key = config.get('etherscan_api_key') or os.getenv('ETHERSCAN_API_KEY', '')
        
        # Cache for Etherscan block numbers
        self._block_cache: Dict[int, str] = {}
    
    def authenticate(self) -> bool:
        """
        Validate that required API keys are available.
        """
        if not self.subgraph_api_key:
            logger.warning("SUBGRAPH_API_KEY not configured - staking data collection disabled")
        if not self.etherscan_api_key:
            logger.warning("ETHERSCAN_API_KEY not configured - transaction data collection disabled")
        # CoinGecko doesn't require API key for basic endpoints
        return True
    
    # =========================================================================
    # STAKING DATA
    # =========================================================================
    
    async def _fetch_staking_data(self, days: int = 365) -> List[Dict]:
        """
        Fetch staking data from The Graph subgraph.
        
        Args:
            days: Number of days of data to fetch
            
        Returns:
            List of staking day data records
        """
        if not self.subgraph_api_key:
            logger.warning("Skipping staking data - no API key")
            return []
        
        endpoint = f"https://gateway.thegraph.com/api/{self.subgraph_api_key}/subgraphs/id/{SUBGRAPH_ID}"
        
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
                    json={"query": query, "variables": {}},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch staking data: {e}")
            return []
        
        staking_datas = data.get("data", {}).get("stakingDayDatas", [])
        return staking_datas
    
    async def collect_staking_data(self) -> Dict[str, Any]:
        """
        Collect and process staking data.
        
        Returns:
            Dict with staking data summary
        """
        logger.info("   📊 Fetching staking data from The Graph...")
        
        raw_data = await self._fetch_staking_data(days=91)
        
        if not raw_data:
            return {"records": [], "latest_staked": 0, "latest_date": None}
        
        # Sort by date ascending
        sorted_data = sorted(raw_data, key=lambda x: x["date"])
        
        # Process records
        records = []
        for item in sorted_data:
            timestamp = int(item["date"])
            total_staked_wei = item["totalStaked"]
            # The Graph staking subgraph uses 27 decimal places
            total_staked_ton = int(total_staked_wei) / 10**27
            
            records.append({
                "date": datetime.utcfromtimestamp(timestamp),
                "timestamp": timestamp,
                "total_staked_wei": total_staked_wei,
                "total_staked_ton": total_staked_ton,
                "collected_at": datetime.utcnow()
            })
        
        latest = records[-1] if records else {}
        
        return {
            "records": records,
            "latest_staked": latest.get("total_staked_ton", 0),
            "latest_date": latest.get("date")
        }
    
    async def save_staking_data(self, data: Dict[str, Any]) -> int:
        """
        Save staking data to MongoDB.
        
        Args:
            data: Staking data from collect_staking_data()
            
        Returns:
            Number of records saved/updated
        """
        if not data.get("records"):
            return 0
        
        db = self.mongo_manager.async_db
        collection = db["ecosystem_staking"]
        
        # Create index if not exists
        await collection.create_index("date", unique=True)
        
        saved_count = 0
        for record in data["records"]:
            try:
                # Upsert by date
                await collection.update_one(
                    {"date": record["date"]},
                    {"$set": record},
                    upsert=True
                )
                saved_count += 1
            except Exception as e:
                logger.warning(f"Failed to save staking record: {e}")
        
        logger.info(f"   ✅ Saved {saved_count} staking records")
        return saved_count
    
    # =========================================================================
    # TRANSACTION DATA
    # =========================================================================
    
    async def _get_block_number(self, timestamp: int, client: httpx.AsyncClient) -> Optional[str]:
        """Get Ethereum block number for a timestamp."""
        if timestamp in self._block_cache:
            return self._block_cache[timestamp]
        
        for attempt in range(3):
            try:
                await asyncio.sleep(0.3 + random.random() * 0.1)
                
                url = (
                    f"https://api.etherscan.io/api"
                    f"?module=block&action=getblocknobytime"
                    f"&timestamp={timestamp}&closest=before"
                    f"&apikey={self.etherscan_api_key}"
                )
                
                response = await client.get(url)
                data = response.json()
                
                if data.get("status") == "1" and data.get("result"):
                    self._block_cache[timestamp] = data["result"]
                    return data["result"]
                    
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                logger.error(f"Failed to get block number: {e}")
        
        return None
    
    async def _get_token_tx_count(
        self,
        contract: str,
        start_time: int,
        end_time: int,
        client: httpx.AsyncClient
    ) -> int:
        """Get token transaction count for a contract within a time range."""
        start_block = await self._get_block_number(start_time, client)
        end_block = await self._get_block_number(end_time, client)
        
        if not start_block or not end_block:
            return 0
        
        all_transactions = []
        page = 1
        
        while True:
            try:
                await asyncio.sleep(0.3)
                
                url = (
                    f"https://api.etherscan.io/api"
                    f"?module=account&action=tokentx"
                    f"&contractaddress={contract}"
                    f"&startblock={start_block}&endblock={end_block}"
                    f"&page={page}&offset=1000&sort=asc"
                    f"&apikey={self.etherscan_api_key}"
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
                else:
                    break
                    
            except Exception as e:
                logger.warning(f"Error fetching transactions page {page}: {e}")
                break
        
        # Filter by timestamp
        filtered = [
            tx for tx in all_transactions
            if start_time <= int(tx.get("timeStamp", 0)) <= end_time
        ]
        
        return len(filtered)
    
    async def collect_transaction_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect TON/WTON transaction counts.
        
        Args:
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Dict with transaction counts
        """
        if not self.etherscan_api_key:
            logger.warning("Skipping transaction data - no API key")
            return {"ton_count": 0, "wton_count": 0}
        
        logger.info("   📊 Fetching TON/WTON transactions from Etherscan...")
        
        start_time = int(start_date.timestamp())
        end_time = int(end_date.timestamp())
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            ton_count = await self._get_token_tx_count(TON_CONTRACT, start_time, end_time, client)
            wton_count = await self._get_token_tx_count(WTON_CONTRACT, start_time, end_time, client)
        
        return {
            "date": end_date.date().isoformat(),
            "period_start": start_date,
            "period_end": end_date,
            "ton_count": ton_count,
            "wton_count": wton_count,
            "total_count": ton_count + wton_count,
            "collected_at": datetime.utcnow()
        }
    
    async def save_transaction_data(self, data: Dict[str, Any]) -> bool:
        """
        Save transaction data to MongoDB.
        
        Args:
            data: Transaction data from collect_transaction_data()
            
        Returns:
            True if saved successfully
        """
        if not data.get("date"):
            return False
        
        db = self.mongo_manager.async_db
        collection = db["ecosystem_transactions"]
        
        # Create index if not exists
        await collection.create_index("date", unique=True)
        
        try:
            await collection.update_one(
                {"date": data["date"]},
                {"$set": data},
                upsert=True
            )
            logger.info(f"   ✅ Saved transaction data: TON={data['ton_count']}, WTON={data['wton_count']}")
            return True
        except Exception as e:
            logger.error(f"Failed to save transaction data: {e}")
            return False
    
    # =========================================================================
    # MARKET CAP DATA
    # =========================================================================
    
    async def collect_market_cap_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Collect market cap data from CoinGecko.
        
        Note: CoinGecko free API has limitations on historical data.
        The /market_chart/range endpoint may return 401 for older dates.
        
        Args:
            start_date: Start of period for price range
            end_date: End of period for price range
            
        Returns:
            Dict with market cap data
        """
        logger.info("   📊 Fetching market cap data from CoinGecko...")
        
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=14)
        
        # Rate limit: wait before API call
        await asyncio.sleep(1.5)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Current market data (this works on free tier)
            current_url = (
                f"https://api.coingecko.com/api/v3/coins/{COINGECKO_TOKEN_ID}"
                f"?localization=false&tickers=false&market_data=true"
                f"&community_data=false&developer_data=false"
            )
            
            try:
                response = await client.get(current_url)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("   ⚠️ CoinGecko rate limit - waiting 60s...")
                    await asyncio.sleep(60)
                    # Retry once
                    response = await client.get(current_url)
                    response.raise_for_status()
                    data = response.json()
                else:
                    logger.error(f"Failed to fetch market data: {e}")
                    return {}
            except Exception as e:
                logger.error(f"Failed to fetch market data: {e}")
                return {}
            
            market_data = data.get("market_data", {})
            
            # Try to get historical price data for high/low
            # Note: This may fail on free tier for older dates
            prices = []
            total_volume = market_data.get("total_volume", {}).get("usd", 0)
            
            # Only try historical data for recent dates (last 30 days)
            days_back = (datetime.utcnow() - start_date).days
            if days_back <= 30:
                start_ts = int(start_date.timestamp())
                end_ts = int(end_date.timestamp())
                
                price_url = (
                    f"https://api.coingecko.com/api/v3/coins/{COINGECKO_TOKEN_ID}"
                    f"/market_chart/range?vs_currency=usd&from={start_ts}&to={end_ts}"
                )
                
                await asyncio.sleep(1.5)  # Rate limit
                
                try:
                    price_response = await client.get(price_url)
                    price_response.raise_for_status()
                    price_data = price_response.json()
                    prices = [p[1] for p in price_data.get("prices", [])]
                    volumes = price_data.get("total_volumes", [])
                    if volumes:
                        total_volume = sum(v[1] for v in volumes)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in [401, 429]:
                        logger.debug(f"   Historical price data unavailable (status {e.response.status_code})")
                    else:
                        logger.warning(f"Failed to fetch price history: {e}")
                except Exception as e:
                    logger.debug(f"   Could not fetch price history: {e}")
            
            # Use current price for high/low if historical data unavailable
            current_price = market_data.get("current_price", {}).get("usd", 0)
            high_24h = market_data.get("high_24h", {}).get("usd", current_price)
            low_24h = market_data.get("low_24h", {}).get("usd", current_price)
            
            return {
                "date": end_date.date().isoformat(),
                "period_start": start_date,
                "period_end": end_date,
                "market_cap_usd": market_data.get("market_cap", {}).get("usd", 0),
                "total_supply": market_data.get("total_supply", 0),
                "current_price_usd": current_price,
                "price_high_usd": max(prices) if prices else high_24h,
                "price_low_usd": min(prices) if prices else low_24h,
                "trading_volume_usd": total_volume,
                "collected_at": datetime.utcnow()
            }
    
    async def save_market_cap_data(self, data: Dict[str, Any]) -> bool:
        """
        Save market cap data to MongoDB.
        
        Args:
            data: Market cap data from collect_market_cap_data()
            
        Returns:
            True if saved successfully
        """
        if not data.get("date"):
            return False
        
        db = self.mongo_manager.async_db
        collection = db["ecosystem_market_cap"]
        
        # Create index if not exists
        await collection.create_index("date", unique=True)
        
        try:
            await collection.update_one(
                {"date": data["date"]},
                {"$set": data},
                upsert=True
            )
            logger.info(f"   ✅ Saved market cap: ${data['market_cap_usd']:,.0f}")
            return True
        except Exception as e:
            logger.error(f"Failed to save market cap data: {e}")
            return False
    
    # =========================================================================
    # ALL-IN-ONE COLLECTION
    # =========================================================================
    
    async def collect_all(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect all ecosystem data.
        
        Args:
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Dict with all collected data
        """
        results = {
            "staking": {"success": False, "count": 0},
            "transactions": {"success": False, "data": {}},
            "market_cap": {"success": False, "data": {}}
        }
        
        # Staking data
        try:
            staking_data = await self.collect_staking_data()
            count = await self.save_staking_data(staking_data)
            results["staking"] = {"success": True, "count": count}
        except Exception as e:
            logger.error(f"Staking collection failed: {e}")
        
        # Transaction data
        try:
            tx_data = await self.collect_transaction_data(start_date, end_date)
            success = await self.save_transaction_data(tx_data)
            results["transactions"] = {"success": success, "data": tx_data}
        except Exception as e:
            logger.error(f"Transaction collection failed: {e}")
        
        # Market cap data
        try:
            market_data = await self.collect_market_cap_data(start_date, end_date)
            success = await self.save_market_cap_data(market_data)
            results["market_cap"] = {"success": success, "data": market_data}
        except Exception as e:
            logger.error(f"Market cap collection failed: {e}")
        
        return results
