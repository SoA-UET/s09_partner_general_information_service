"""
Partner Information Service (S09)
Manages partner connection information and provides it to other services.
"""

from pymongo.collection import Collection
from .common.BaseCRUDService import BaseCRUDService
from datetime import datetime
from typing import Any
import requests
import os


class PartnerInformationService(BaseCRUDService):
    """
    Service for managing partner general information.
    This service handles the single partner information record.
    """
    
    def __init__(self, collection: Collection):
        super().__init__(collection=collection, enable_timing=True)
        self._event_listeners: list = []
    
    def register_event_listener(self, listener):
        """
        Register a listener for core_update events.
        Listener should be a callable that accepts (event_name, params).
        """
        self._event_listeners.append(listener)
    
    def _notify_core_update(self, partner_info: dict):
        """Notify all listeners about core connection update."""
        params = {
            "partner_id": partner_info.get("partner_id", ""),
            "name": partner_info.get("name", ""),
            "api_key": partner_info.get("api_key", ""),
            "core_url": partner_info.get("core_url", ""),
        }
        for listener in self._event_listeners:
            try:
                listener("core_update", params)
            except Exception as e:
                print(f"[PartnerInformationService] Error notifying listener: {e}")
    
    def get_partner_info(self) -> dict | None:
        """
        Get the single partner information record.
        Returns None if no record exists.
        """
        result = self.collection.find_one({})
        return result
    
    def update_partner_info(self, update_data: dict) -> dict:
        """
        Update the partner information. Creates it if it doesn't exist.
        Returns the updated record.
        """
        now = datetime.now()
        
        existing = self.collection.find_one({})
        
        if existing:
            # Update existing record
            update_data["updated_at"] = now
            result = self.collection.find_one_and_update(
                {"_id": existing["_id"]},
                {"$set": update_data},
                return_document=True
            )
        else:
            # Create new record
            update_data["created_at"] = now
            update_data["updated_at"] = now
            insert_result = self.collection.insert_one(update_data)
            result = self.collection.find_one({"_id": insert_result.inserted_id})
        
        # Notify listeners about the update (A12b event)
        if result:
            self._notify_core_update(result)
        
        return result
    
    def get_core_info(self) -> dict:
        """
        Get core connection information for internal Partner services (A12a).
        Returns partner_id, api_key, and core_url.
        """
        partner_info = self.get_partner_info()
        
        if not partner_info:
            raise ValueError("Partner information not configured")
        
        return {
            "partner_id": partner_info.get("partner_id", ""),
            "api_key": partner_info.get("api_key", ""),
            "core_url": partner_info.get("core_url", ""),
        }
    
    def test_core_connection(self, core_url: str, api_key: str) -> dict:
        """
        Test connection to Telcenter Core by calling H11 API.
        Returns partner_id on success, raises exception on failure.
        """
        # Extract partner_id from existing info or use empty string for verification
        partner_info = self.get_partner_info()
        partner_id = partner_info.get("partner_id", "") if partner_info else ""
        
        # If partner_id is empty, we need to get it from api_key
        # The Core system should be able to identify the partner from the api_key
        if not partner_id:
            partner_id = "verify"  # Placeholder for initial verification
        
        # Call H11 API: POST /api/v1/partners/:id/verify-connection
        url = f"{core_url.rstrip('/')}/api/v1/partners/{partner_id}/verify-connection"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, timeout=30)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status") == "success":
                return {
                    "partner_id": response_data.get("data", {}).get("partner_id", "")
                }
            else:
                error_msg = response_data.get("message", "Connection verification failed")
                raise ConnectionError(error_msg)
                
        except requests.exceptions.Timeout:
            raise ConnectionError("Connection to Core timed out")
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Could not connect to Core")
        except requests.exceptions.JSONDecodeError:
            raise ConnectionError("Invalid response from Core")
