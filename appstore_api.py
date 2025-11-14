import requests
import auth
import config
from typing import List, Dict, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class AppStoreConnectAPI:
    def __init__(self):
        self.base_url = config.API_BASE_URL
        self.token = None
    
    def _get_token(self):
        """Get or refresh the authentication token"""
        if not self.token:
            self.token = auth.generate_token()
        return self.token
    
    def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Dict:
        """Make an API request to App Store Connect"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }
        
        response = requests.request(method, url, headers=headers, params=params, json=json_data)
        if not response.ok:
            error_msg = f"{response.status_code} {response.reason}"
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_details = error_data["errors"]
                    error_msg += f": {error_details}"
                else:
                    error_msg += f": {error_data}"
            except:
                error_msg += f": {response.text[:500]}"
            raise requests.exceptions.HTTPError(error_msg, response=response)
        return response.json()
    
    def get_subscription_groups(self, app_id: str) -> List[Dict]:
        """Get all subscription groups for an app"""
        endpoint = f"/apps/{app_id}/subscriptionGroups"
        data = self._make_request(endpoint)
        return data.get("data", [])
    
    def get_subscriptions_in_group(self, group_id: str) -> List[Dict]:
        """Get all subscriptions in a subscription group"""
        endpoint = f"/subscriptionGroups/{group_id}/subscriptions"
        data = self._make_request(endpoint)
        return data.get("data", [])
    
    def get_subscription_details(self, subscription_id: str) -> Dict:
        """Get detailed information about a subscription"""
        endpoint = f"/subscriptions/{subscription_id}"
        params = {
            "include": "prices,subscriptionLocalizations"
        }
        data = self._make_request(endpoint, params=params)
        return data.get("data", {})
    
    def get_subscription_prices(self, subscription_id: str) -> List[Dict]:
        """Get all prices for a subscription"""
        endpoint = f"/subscriptions/{subscription_id}/prices"
        params = {
            "include": "subscriptionPricePoint"
        }
        data = self._make_request(endpoint, params=params)
        return data.get("data", [])
    
    def get_price_tiers(self) -> List[Dict]:
        """Get all available price tiers"""
        endpoint = "/subscriptionPricePoints"
        data = self._make_request(endpoint)
        return data.get("data", [])
    
    def update_subscription_price(self, subscription_id: str, price_point_id: str, start_date: Optional[str] = None) -> Dict:
        """
        Update subscription price by creating a new price schedule
        Uses POST /v1/subscriptionPrices endpoint
        Reference: https://developer.apple.com/documentation/appstoreconnectapi/post-v1-subscriptionprices
        start_date: ISO 8601 date string (e.g., "2025-11-15") or None for immediate
        """
        endpoint = "/subscriptionPrices"
        
        data_payload = {
            "type": "subscriptionPrices",
            "relationships": {
                "subscription": {
                    "data": {
                        "type": "subscriptions",
                        "id": subscription_id
                    }
                },
                "subscriptionPricePoint": {
                    "data": {
                        "type": "subscriptionPricePoints",
                        "id": price_point_id
                    }
                }
            }
        }
        
        # startDate is required for price changes (cannot create immediate changes after subscription is approved)
        # If not provided, use tomorrow as default
        if not start_date:
            from datetime import datetime, timedelta
            start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        data_payload["attributes"] = {
            "startDate": start_date
        }
        
        json_data = {
            "data": data_payload
        }
        
        data = self._make_request(endpoint, method="POST", json_data=json_data)
        return data.get("data", {})
    
    def delete_subscription_price(self, price_entry_id: str) -> Dict:
        """
        Delete a scheduled subscription price change
        Uses DELETE /v1/subscriptionPrices/{id} endpoint
        Reference: https://developer.apple.com/documentation/appstoreconnectapi/delete-v1-subscriptionprices-_id_
        """
        endpoint = f"/subscriptionPrices/{price_entry_id}"
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }
        
        response = requests.delete(url, headers=headers)
        if not response.ok:
            error_msg = f"{response.status_code} {response.reason}"
            try:
                error_data = response.json()
                if "errors" in error_data:
                    error_details = error_data["errors"]
                    error_msg += f": {error_details}"
                else:
                    error_msg += f": {error_data}"
            except:
                error_msg += f": {response.text[:500]}"
            raise requests.exceptions.HTTPError(error_msg, response=response)
        
        # DELETE may return empty response (204 No Content)
        if response.text:
            return response.json()
        return {"status": "deleted"}
    
    def _make_parallel_requests(self, requests_list: List[Callable[[], Any]], max_workers: int = 10, retry_on_rate_limit: bool = True) -> List[Any]:
        """
        Make multiple API requests in parallel
        
        Args:
            requests_list: List of callable functions that return API responses
            max_workers: Maximum number of concurrent requests (default: 10)
            retry_on_rate_limit: Whether to retry on 429 rate limit errors (default: True)
        
        Returns:
            List of results in the same order as requests_list (None for failed requests)
        """
        results = [None] * len(requests_list)
        rate_limited_indices = []
        
        def make_request_with_index(index: int, request_func: Callable[[], Any]) -> tuple[int, Any]:
            """Wrapper to track index of request"""
            try:
                return (index, request_func())
            except requests.exceptions.HTTPError as e:
                # Check if it's a rate limit error (429)
                if retry_on_rate_limit and hasattr(e.response, 'status_code') and e.response.status_code == 429:
                    return (index, "RATE_LIMITED")
                # For other errors, return None (will be handled)
                return (index, None)
            except Exception:
                return (index, None)
        
        # First pass: Make parallel requests
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(make_request_with_index, idx, req): idx 
                for idx, req in enumerate(requests_list)
            }
            
            completed = 0
            for future in as_completed(future_to_index):
                completed += 1
                if completed % 10 == 0:
                    print(f"    → Completed {completed}/{len(requests_list)} requests...")
                
                try:
                    index, result = future.result()
                    if result == "RATE_LIMITED":
                        rate_limited_indices.append(index)
                    elif result is not None:
                        results[index] = result
                except Exception:
                    pass
        
        # Second pass: Retry rate-limited requests with exponential backoff
        if rate_limited_indices and retry_on_rate_limit:
            print(f"    ⚠️  {len(rate_limited_indices)} requests rate-limited, retrying with backoff...")
            wait_time = 1  # Start with 1 second
            
            for attempt in range(3):  # Max 3 retry attempts
                time.sleep(wait_time)
                retry_requests = [requests_list[idx] for idx in rate_limited_indices]
                
                with ThreadPoolExecutor(max_workers=5) as executor:  # Lower concurrency for retries
                    retry_futures = {
                        executor.submit(make_request_with_index, rate_limited_indices[idx], req): idx
                        for idx, req in enumerate(retry_requests)
                    }
                    
                    still_rate_limited = []
                    successful_indices = []
                    for future in as_completed(retry_futures):
                        try:
                            index, result = future.result()
                            if result == "RATE_LIMITED":
                                still_rate_limited.append(index)
                            elif result is not None:
                                results[index] = result
                                successful_indices.append(index)
                        except Exception:
                            pass
                    
                    # Remove successful indices from rate_limited_indices
                    rate_limited_indices = [idx for idx in rate_limited_indices if idx not in successful_indices]
                
                if not still_rate_limited:
                    break
                
                rate_limited_indices = still_rate_limited
                wait_time *= 2  # Exponential backoff: 1s, 2s, 4s
            
            if rate_limited_indices:
                print(f"    ⚠️  {len(rate_limited_indices)} requests still rate-limited after retries")
        
        return results

