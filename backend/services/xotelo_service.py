"""
Xotelo Hotel Pricing Service via RapidAPI (ASYNC)

Provides:
- Real-time hotel pricing from 200+ OTAs
- Price comparison across booking sites
- Day heatmap for finding cheapest dates
- Hotel search by name/location
- Batch concurrent pricing for multiple hotels

API: https://rapidapi.com/anastue-pGK7lGUO-Wo/api/xotelo-hotel-prices
Pricing: Free tier = 1,000 requests/month
Location: backend/services/xotelo_service.py

Changes (RapidAPI migration):
  - BASE_URL changed to RapidAPI proxy host
  - Auth via X-RapidAPI-Key + X-RapidAPI-Host headers (not query params)
  - MAX_CONCURRENT_REQUESTS lowered to 2 (respect free tier per-second limit)
  - REQUEST_DELAY of 0.6s after each call to avoid 429 rate limiting
  - Headers injected into httpx.AsyncClient, not per-request params
  - Single-hotel dict responses wrapped into lists (Xotelo inconsistency)

Changes (async refactor):
  - Replaced requests.Session with httpx.AsyncClient
  - All HTTP methods are now async
  - Added batch_get_prices() for concurrent multi-hotel pricing
  - Semaphore limits concurrent requests to respect rate limits
  - Callers use asyncio.run() to bridge from sync Celery tasks
  - No more singleton session — AsyncClient is created per-batch via context manager
"""
import asyncio
import logging
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from config.settings import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Max concurrent requests (free tier has strict per-second rate limits)
# 1 = sequential but reliable; 2 = light overlap, still safe
MAX_CONCURRENT_REQUESTS = 3

# Delay between requests to avoid RapidAPI 429 rate limiting (seconds)
# Free tier enforces per-second limits stricter than the 1,000/hour quota
REQUEST_DELAY = 0.4

# Timeout per individual HTTP request (seconds)
REQUEST_TIMEOUT = 10.0

# RapidAPI configuration
RAPIDAPI_HOST = "xotelo-hotel-prices.p.rapidapi.com"
RAPIDAPI_BASE_URL = f"https://{RAPIDAPI_HOST}/api"


class XoteloService:
    """
    Async service for Xotelo Hotel Pricing API via RapidAPI.
    
    All HTTP methods are async. For use in sync contexts (e.g. Celery tasks),
    call via asyncio.run():
    
        pricing = asyncio.run(xotelo.get_price_for_hotel(...))
        results = asyncio.run(xotelo.batch_get_prices(hotels, ...))
    """
    
    BASE_URL = RAPIDAPI_BASE_URL
    
    def __init__(self, rapidapi_key: Optional[str] = None):
        """
        Initialize Xotelo service with RapidAPI credentials.
        
        Note: No persistent session/client is stored. An httpx.AsyncClient is
        created per batch operation via context manager, avoiding stale
        connections on long-lived Celery workers.
        
        Args:
            rapidapi_key: RapidAPI key for authentication (required)
        """
        self.rapidapi_key = rapidapi_key
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        if self.rapidapi_key:
            logger.info("✅ Xotelo API initialized with RapidAPI key (async)")
        else:
            logger.warning("⚠️  Xotelo API initialized WITHOUT RapidAPI key — all calls will fail")
    
    def _get_headers(self) -> Dict[str, str]:
        """Build RapidAPI auth headers."""
        return {
            "X-RapidAPI-Key": self.rapidapi_key or "",
            "X-RapidAPI-Host": RAPIDAPI_HOST,
        }
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """
        Get or create semaphore for the current event loop.
        
        Semaphores are bound to an event loop, so we create a new one
        each time asyncio.run() starts a fresh loop.
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        return self._semaphore
    
    # ─────────────────────────────────────────────────────────────────────
    # CORE ASYNC HTTP METHODS
    # ─────────────────────────────────────────────────────────────────────

    async def search_hotels(
        self,
        client: httpx.AsyncClient,
        query: str,
        agent_logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels by name or location.
        
        Args:
            client: Shared httpx.AsyncClient (from batch context)
            query: Hotel name or location (e.g., "Grand Plaza London")
            agent_logger: Optional agent-specific logger
            
        Returns:
            List of hotel dictionaries with hotel_key and basic info
        """
        log = agent_logger or logger
        sem = self._get_semaphore()
        
        try:
            async with sem:
                # log.info(f"🔍 Searching Xotelo for: {query}")
                
                url = f"{self.BASE_URL}/search"
                params = {'query': query}
                
                response = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # Rate-limit: pause before releasing semaphore
                await asyncio.sleep(REQUEST_DELAY)
                
                raw_data = response.json()
                
                # Debug: log raw Xotelo response shape to diagnose parsing issues
                # if isinstance(raw_data, dict):
                #     log.info(
                #         f"🔬 Xotelo search response: "
                #         f"error={raw_data.get('error')!r}, "
                #         f"result_type={type(raw_data.get('result')).__name__}, "
                #         f"result_len={len(raw_data.get('result', [])) if isinstance(raw_data.get('result'), (list, dict)) else 'N/A'}"
                #     )
                # elif isinstance(raw_data, list) and raw_data:
                #     first_item = raw_data[0]
                #     item_info = (
                #         list(first_item.keys()) 
                #         if isinstance(first_item, dict) 
                #         else type(first_item).__name__
                #     )
                    # log.info(
                    #     f"🔬 Xotelo search response is list[{len(raw_data)}], "
                    #     f"first item: {item_info}"
                    # )
                
                data = raw_data
                
                # Xotelo returns {"error": ..., "result": [...], "timestamp": ...}
                # RapidAPI may nest further: {"error": ..., "result": {"results": [...], ...}}
                # Normalize to list with up to 2 levels of unwrapping
                if isinstance(data, dict):
                    # Log any error from Xotelo
                    xotelo_error = data.get('error')
                    if xotelo_error is not None and xotelo_error != False:
                        log.warning(f"⚠️  Xotelo error field: {xotelo_error!r}")
                    
                    data = (
                        data.get('result')
                        or data.get('results')
                        or data.get('data')
                        or data.get('hotels')
                        or []
                    )
                
                # Second-level unwrap: if 'result' was itself a dict (RapidAPI extra nesting)
                if isinstance(data, dict):
                    types_preview = {k: type(v).__name__ for k, v in data.items()}
                    # log.info(
                    #     f"🔬 Nested dict after first unwrap, keys={list(data.keys())}, "
                    #     f"types={types_preview}"
                    # )
                    inner = (
                        data.get('result')
                        or data.get('results')
                        or data.get('data')
                        or data.get('hotels')
                        or data.get('list')
                    )
                    if inner is not None:
                        data = inner
                    elif 'hotel_key' in data or 'key' in data or 'name' in data:
                        # It's actually a single hotel object
                        # log.info(f"ℹ️  Single hotel result (dict), wrapping in list")
                        data = [data]
                    else:
                        dump_preview = {k: str(v)[:100] for k, v in data.items()}
                        # log.warning(
                        #     f"⚠️  Unknown dict structure, dumping: {dump_preview}"
                        # )
                        data = []
                
                if not data:
                    log.warning(f"⚠️  No hotels found for: {query}")
                    return []
                
                # Final: if still a dict (single hotel from second unwrap), wrap in list
                if isinstance(data, dict):
                    data = [data]
                
                if not isinstance(data, list):
                    log.warning(f"⚠️  Unexpected Xotelo response type: {type(data).__name__}")
                    return []
                
                # log.info(f"✅ Found {len(data)} hotels in Xotelo")
                return data
                
        except httpx.TimeoutException:
            log.error(f"❌ Xotelo search timeout for: {query}")
            return []
        except httpx.HTTPStatusError as e:
            log.error(f"❌ Xotelo search HTTP error: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            log.error(f"❌ Xotelo search error: {e}")
            return []
        except Exception as e:
            log.error(f"❌ Unexpected error in Xotelo search: {e}")
            return []
    
    async def get_hotel_rates(
        self,
        client: httpx.AsyncClient,
        hotel_key: str,
        check_in_date: str,
        check_out_date: str,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get pricing for a specific hotel.
        
        Args:
            client: Shared httpx.AsyncClient
            hotel_key: Xotelo hotel key (from search results)
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with pricing information from all OTAs
        """
        log = agent_logger or logger
        sem = self._get_semaphore()
        
        try:
            async with sem:
                # log.info(f"💰 Getting rates for hotel_key: {hotel_key}")
                
                url = f"{self.BASE_URL}/rates"
                params = {
                    'hotel_key': hotel_key,
                    'chk_in': check_in_date,
                    'chk_out': check_out_date
                }
                
                response = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # Rate-limit: pause before releasing semaphore
                await asyncio.sleep(REQUEST_DELAY)
                
                data = response.json()
                
                # Debug: log raw rates response shape
                # if isinstance(data, dict):
                #     log.info(
                #         f"🔬 Rates raw response keys: {list(data.keys())}"
                #     )
                
                # Xotelo wraps rates in {"error": ..., "result": {...}, "timestamp": ...}
                if isinstance(data, dict) and 'result' in data:
                    xotelo_error = data.get('error')
                    if xotelo_error:
                        log.warning(f"⚠️  Xotelo rates error field: {xotelo_error}")
                    data = data.get('result')
                
                # Debug: log unwrapped rates structure
                # if isinstance(data, dict):
                #     log.info(
                #         f"🔬 Rates after unwrap keys: {list(data.keys())}, "
                #         f"providers type: {type(data.get('providers')).__name__}"
                #     )
                    # ── DIAGNOSTIC: dump full rates response for first hotels ──
                    # This helps verify if rate/tax are per-night or total-stay
                    # import json as _json
                    # try:
                    #     rates_preview = data.get('rates', [])
                    #     if rates_preview and isinstance(rates_preview, list):
                            # log.info(
                            #     f"🔬 DIAG full rates dump ({len(rates_preview)} providers): "
                            #     f"{_json.dumps(rates_preview, indent=None)[:800]}"
                            # )
                        # log.info(
                        #     f"🔬 DIAG response metadata: "
                        #     f"chk_in={data.get('chk_in')}, "
                        #     f"chk_out={data.get('chk_out')}, "
                        #     f"currency={data.get('currency')}"
                        # )
                    # except Exception:
                    #     pass
                
                if not data:
                    log.warning(f"⚠️  No rates found for hotel_key: {hotel_key}")
                    return None
                
                rate_count = len(data.get('rates', data.get('providers', [])))
                # log.info(f"✅ Retrieved rates from {rate_count} OTAs")
                return data
                
        except httpx.TimeoutException:
            log.error(f"❌ Xotelo rates timeout for: {hotel_key}")
            return None
        except httpx.HTTPStatusError as e:
            log.error(f"❌ Xotelo rates HTTP error: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            log.error(f"❌ Xotelo rates error: {e}")
            return None
        except Exception as e:
            log.error(f"❌ Unexpected error getting rates: {e}")
            return None
    
    async def get_price_for_hotel(
        self,
        client: httpx.AsyncClient,
        hotel_name: str,
        check_in_date: str,
        check_out_date: str,
        location: Optional[str] = None,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Complete workflow: Search hotel + Get pricing (async).
        
        Args:
            client: Shared httpx.AsyncClient
            hotel_name: Name of the hotel
            check_in_date: Check-in date (YYYY-MM-DD)
            check_out_date: Check-out date (YYYY-MM-DD)
            location: Optional location to help narrow search
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with parsed pricing information
        """
        log = agent_logger or logger
        
        # Step 1: Search for hotel
        query = f"{hotel_name} {location}" if location else hotel_name
        search_results = await self.search_hotels(client, query, agent_logger=log)
        
        if not search_results:
            log.warning(f"⚠️  Could not find hotel: {hotel_name}")
            return None
        
        # Validate search_results is a list of dicts
        if not isinstance(search_results, list) or not isinstance(search_results[0], dict):
            log.warning(
                f"⚠️  Unexpected search result type for '{hotel_name}': "
                f"{type(search_results).__name__}"
                f"[0]={type(search_results[0]).__name__ if search_results else 'empty'}"
            )
            return None
        
        # Take first result (best match)
        hotel = search_results[0]
        
        # Debug: log what keys the hotel dict actually has
        # log.info(f"🔬 Hotel result keys: {list(hotel.keys())}")
        
        # Try multiple possible key names (Xotelo direct vs RapidAPI may differ)
        hotel_key = (
            hotel.get('hotel_key')
            or hotel.get('key')
            or hotel.get('hotelKey')
            or hotel.get('id')
        )
        
        if not hotel_key:
            values_preview = {k: str(v)[:60] for k, v in hotel.items()}
            log.warning(
                f"⚠️  No hotel_key in search results. "
                f"Available keys: {list(hotel.keys())}, "
                f"values: {values_preview}"
            )
            return None
        
        # log.info(f"✓ Found hotel: {hotel.get('name', 'Unknown')} (key: {hotel_key})")
        
        # Step 2: Get rates
        rates_data = await self.get_hotel_rates(
            client=client,
            hotel_key=hotel_key,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            agent_logger=log
        )
        
        if not rates_data:
            return None
        
        # Step 3: Parse and return best pricing
        return self._parse_pricing_data(rates_data, check_in_date, check_out_date, log)
    
    # ─────────────────────────────────────────────────────────────────────
    # BATCH CONCURRENT PRICING — the main performance win
    # ─────────────────────────────────────────────────────────────────────

    async def batch_get_prices(
        self,
        hotels: List[Dict[str, Any]],
        destination: str,
        check_in_date: str,
        check_out_date: str,
        agent_logger: Optional[logging.Logger] = None,
        on_progress: Optional[Any] = None,
    ) -> List[Tuple[int, Optional[Dict[str, Any]]]]:
        """
        Fetch pricing for multiple hotels concurrently.
        
        This is the key method that replaces the sequential loop in
        _enrich_hotels_with_pricing. Instead of 30 sequential calls
        taking ~30s, all 30 run concurrently in ~1-2s.
        
        Args:
            hotels: List of Google Places hotel dicts (need 'name' field)
            destination: City/location for Xotelo search context
            check_in_date: YYYY-MM-DD
            check_out_date: YYYY-MM-DD
            agent_logger: Optional logger
            on_progress: Optional async callback(index, hotel_name, pricing)
                         for status updates during enrichment
            
        Returns:
            List of (index, pricing_dict_or_None) tuples, in original order
        """
        log = agent_logger or logger
        
        # Reset semaphore for this event loop
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        
        # log.info(
        #     f"🚀 Batch pricing: {len(hotels)} hotels, "
        #     f"max {MAX_CONCURRENT_REQUESTS} concurrent"
        # )
        
        async with httpx.AsyncClient(headers=self._get_headers()) as client:
            tasks = [
                self._fetch_single_hotel_price(
                    client=client,
                    index=idx,
                    hotel_name=hotel.get('name', 'Unknown'),
                    destination=destination,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    agent_logger=log,
                    on_progress=on_progress,
                )
                for idx, hotel in enumerate(hotels)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to None
        processed = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(f"❌ Hotel {idx} pricing exception: {result}")
                processed.append((idx, None))
            else:
                processed.append(result)
        
        # success_count = sum(1 for _, pricing in processed if pricing is not None)
        # log.info(
        #     f"✅ Batch complete: {success_count}/{len(hotels)} hotels priced"
        # )
        
        return processed
    
    async def _fetch_single_hotel_price(
        self,
        client: httpx.AsyncClient,
        index: int,
        hotel_name: str,
        destination: str,
        check_in_date: str,
        check_out_date: str,
        agent_logger: Optional[logging.Logger] = None,
        on_progress: Optional[Any] = None,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        """
        Fetch pricing for a single hotel (used as a gather task).
        
        Returns (index, pricing) to maintain ordering.
        Individual failures return (index, None) — never raises.
        """
        log = agent_logger or logger
        pricing = None
        
        try:
            pricing = await self.get_price_for_hotel(
                client=client,
                hotel_name=hotel_name,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                location=destination,
                agent_logger=log,
            )
        except Exception as e:
            log.error(
                f"❌ Xotelo pricing failed for '{hotel_name}': "
                f"{type(e).__name__}: {e}"
            )
        
        # Optional progress callback for status updates
        if on_progress:
            try:
                await on_progress(index, hotel_name, pricing)
            except Exception:
                pass  # Status updates are non-critical
        
        return (index, pricing)
    
    # ─────────────────────────────────────────────────────────────────────
    # HEATMAP (also async now)
    # ─────────────────────────────────────────────────────────────────────

    async def get_price_heatmap(
        self,
        client: httpx.AsyncClient,
        hotel_key: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        agent_logger: Optional[logging.Logger] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get price heatmap showing cheapest/expensive days.
        
        Args:
            client: Shared httpx.AsyncClient
            hotel_key: Xotelo hotel key
            month: Month (1-12, optional — defaults to current)
            year: Year (optional — defaults to current)
            agent_logger: Optional agent-specific logger
            
        Returns:
            Dictionary with heatmap data
        """
        log = agent_logger or logger
        sem = self._get_semaphore()
        
        try:
            async with sem:
                log.info(f"📊 Getting price heatmap for hotel_key: {hotel_key}")
                
                params: Dict[str, Any] = {'hotel_key': hotel_key}
                if month:
                    params['month'] = month
                if year:
                    params['year'] = year
                
                url = f"{self.BASE_URL}/heatmap"
                response = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                
                # Rate-limit: pause before releasing semaphore
                await asyncio.sleep(REQUEST_DELAY)
                
                data = response.json()
                # log.info("✅ Retrieved price heatmap")
                return data
                
        except Exception as e:
            log.error(f"❌ Error getting heatmap: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # PRICING PARSER (sync — no HTTP, just data transformation)
    # ─────────────────────────────────────────────────────────────────────

    def _parse_pricing_data(
        self,
        data: Dict[str, Any],
        check_in: str,
        check_out: str,
        log: logging.Logger
    ) -> Optional[Dict[str, Any]]:
        """
        Parse Xotelo pricing response.
        
        RapidAPI format:
          {
            "chk_in": "2026-02-23", "chk_out": "2026-02-28", "currency": "USD",
            "rates": [
              {"code": "BookingCom", "name": "Booking.com", "rate": 980, "tax": 240},
              {"code": "Expedia", "name": "Expedia.com", "rate": 967, "tax": 239},
              ...
            ]
          }
        
        Returns structured pricing data with:
        - Best price, average price, price per night, total price
        - Cheapest provider name
        - All provider prices
        """
        try:
            check_in_dt = datetime.strptime(check_in, "%Y-%m-%d")
            check_out_dt = datetime.strptime(check_out, "%Y-%m-%d")
            num_nights = (check_out_dt - check_in_dt).days
            
            if num_nights <= 0:
                log.warning("⚠️  Invalid date range")
                return None
            
            currency = data.get('currency', 'USD')
            
            # ── DIAGNOSTIC: check if API returned different dates than requested ──
            api_chk_in = data.get('chk_in', 'N/A')
            api_chk_out = data.get('chk_out', 'N/A')
            dates_match = (api_chk_in == check_in and api_chk_out == check_out)
            # log.info(
            #     f"🔬 DIAG dates: requested={check_in}→{check_out} ({num_nights}n), "
            #     f"API returned={api_chk_in}→{api_chk_out}, match={dates_match}"
            # )
            
            # RapidAPI format: "rates" is a list of provider dicts
            rates = data.get('rates', [])
            
            # ── DIAGNOSTIC: dump raw rate/tax for first 3 providers ──
            # if rates and isinstance(rates, list):
            #     preview_count = min(10, len(rates))
            #     for i in range(preview_count):
            #         r = rates[i]
                    # if isinstance(r, dict):
                        # log.info(
                        #     f"🔬 DIAG provider[{i}]: name={r.get('name')}, "
                        #     f"rate={r.get('rate')}, tax={r.get('tax')}, "
                        #     f"code={r.get('code')}, "
                        #     f"all_keys={list(r.keys())}"
                        # )
            
            # Legacy fallback: old Xotelo direct format used "providers" dict
            providers = data.get('providers', {})
            
            all_prices = []
            provider_list = []
            
            if rates and isinstance(rates, list):
                # --- RapidAPI format: list of {"name", "rate", "tax", "code"} ---
                for provider in rates:
                    if not isinstance(provider, dict):
                        continue
                    rate = provider.get('rate')
                    if rate is None:
                        continue
                    price_per_night = float(rate)
                    tax_per_night = float(provider.get('tax', 0))
                    nightly_total = price_per_night + tax_per_night
                    stay_total = nightly_total * num_nights
                    all_prices.append(stay_total)
                    provider_list.append({
                        'provider': provider.get('name', provider.get('code', 'Unknown')),
                        'total_price': round(stay_total, 2),
                        'price_per_night': round(nightly_total, 2),
                        'rate': round(price_per_night, 2),
                        'tax': round(tax_per_night, 2),
                        'url': provider.get('url'),
                    })
            elif providers and isinstance(providers, dict):
                # --- Legacy format: dict of {"ProviderName": {"price": N, "url": "..."}} ---
                for provider_name, provider_data in providers.items():
                    if isinstance(provider_data, dict) and 'price' in provider_data:
                        price = float(provider_data['price'])
                        all_prices.append(price)
                        provider_list.append({
                            'provider': provider_name,
                            'total_price': price,
                            'price_per_night': round(price / num_nights, 2),
                            'url': provider_data.get('url'),
                        })
            
            if not all_prices:
                log.warning("⚠️  No valid prices found")
                return None
            
            best_price = min(all_prices)
            avg_price = sum(all_prices) / len(all_prices)
            cheapest_provider = min(provider_list, key=lambda x: x['total_price'])
            
            # ── DIAGNOSTIC: show price math for cheapest provider ──
            # log.info(
            #     f"🔬 DIAG cheapest: provider={cheapest_provider['provider']}, "
            #     f"rate={cheapest_provider.get('rate', 'N/A')}, "
            #     f"tax={cheapest_provider.get('tax', 'N/A')}, "
            #     f"rate+tax={best_price:.2f}, "
            #     f"÷{num_nights}nights=${best_price/num_nights:.2f}/night"
            # )
            # # ── DIAGNOSTIC: show price range across all providers ──
            # max_price = max(all_prices)
            # log.info(
            #     f"🔬 DIAG range: cheapest=${best_price:.2f}, "
            #     f"most_expensive=${max_price:.2f}, "
            #     f"avg=${avg_price:.2f}, "
            #     f"providers={len(all_prices)}"
            # )
            
            pricing = {
                'total_price': round(best_price, 2),
                'price_per_night': round(best_price / num_nights, 2),
                'currency': currency,
                'num_nights': num_nights,
                'price_source': 'xotelo',
                'is_estimated': False,
                'average_price': round(avg_price, 2),
                'cheapest_provider': cheapest_provider['provider'],
                'cheapest_url': cheapest_provider.get('url'),
                'num_providers': len(all_prices),
                'all_providers': provider_list
            }
            
            # log.info(
            #     f"✅ Parsed pricing: ${pricing['total_price']:.2f} total "
            #     f"(${pricing['price_per_night']:.2f}/night) "
            #     f"from {pricing['cheapest_provider']}"
            # )
            
            return pricing
            
        except Exception as e:
            log.error(f"❌ Error parsing pricing data: {e}")
            return None


# ============================================================================
# SINGLETON INSTANCE — LAZY INITIALIZATION
# ============================================================================

_xotelo_service_instance = None


def get_xotelo_service() -> XoteloService:
    """Get singleton instance of XoteloService (lazy initialization)."""
    global _xotelo_service_instance
    
    if _xotelo_service_instance is None:
        rapidapi_key = getattr(settings, 'xotelo_rapidapi_key', None)
        _xotelo_service_instance = XoteloService(rapidapi_key=rapidapi_key)
    
    return _xotelo_service_instance