"""
JWT Authentication Utilities

Implements JWKS-based JWT verification according to the Identity Service specification.
"""

import os
import jwt
import threading
import time
import requests
from functools import wraps
from flask import request, jsonify, g
from typing import Callable, Any
from datetime import datetime


class JWKSManager:
    """
    Manages JWKS (JSON Web Key Set) fetching and caching.
    Refreshes keys on a TTL schedule.
    """
    
    def __init__(self):
        self._keys: dict[str, dict] = {}  # kid -> key data
        self._lock = threading.Lock()
        self._last_refresh: float = 0
        self._refresh_thread: threading.Thread | None = None
        self._running = False
        
        # Get configuration from environment
        self._identity_service_url = os.getenv("IDENTITY_SERVICE_URL", "")
        self._ttl_minutes = int(os.getenv("JWKS_TTL_IN_MINUTES", "10"))
    
    def start(self):
        """Start the JWKS refresh background thread."""
        if not self._identity_service_url:
            print("[JWKSManager] Warning: IDENTITY_SERVICE_URL not configured")
            return
        
        self._running = True
        self._refresh_jwks()  # Initial fetch at startup
        
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()
    
    def stop(self):
        """Stop the JWKS refresh background thread."""
        self._running = False
    
    def _refresh_loop(self):
        """Background loop to refresh JWKS on TTL schedule."""
        while self._running:
            time.sleep(self._ttl_minutes * 60)
            if self._running:
                self._refresh_jwks()
    
    def _refresh_jwks(self):
        """Fetch JWKS from Identity Service."""
        if not self._identity_service_url:
            return
        
        try:
            url = f"{self._identity_service_url.rstrip('/')}/.well-known/jwks.json"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                keys_data = response.json()
                
                with self._lock:
                    # Handle both single key and array of keys
                    if isinstance(keys_data, list):
                        for key_data in keys_data:
                            kid = key_data.get("kid")
                            if kid:
                                self._keys[kid] = key_data
                    elif isinstance(keys_data, dict):
                        # Check if it's a JWKS with "keys" array
                        if "keys" in keys_data:
                            for key_data in keys_data["keys"]:
                                kid = key_data.get("kid")
                                if kid:
                                    self._keys[kid] = key_data
                        else:
                            # Single key object
                            kid = keys_data.get("kid")
                            if kid:
                                self._keys[kid] = keys_data
                    
                    self._last_refresh = time.time()
                
                print(f"[JWKSManager] Successfully refreshed JWKS, {len(self._keys)} keys loaded")
            else:
                print(f"[JWKSManager] Warning: Failed to fetch JWKS, status {response.status_code}")
                
        except Exception as e:
            print(f"[JWKSManager] Warning: Failed to refresh JWKS: {e}")
            # Continue using cached keys (graceful degradation)
    
    def get_public_key(self, kid: str) -> str | None:
        """
        Get the public key for a given key ID.
        Returns None if not found.
        Does NOT refresh JWKS on unknown kid (to prevent DoS).
        """
        with self._lock:
            key_data = self._keys.get(kid)
            if key_data:
                return key_data.get("public_key")
        return None


# Global JWKS manager instance
_jwks_manager: JWKSManager | None = None


def get_jwks_manager() -> JWKSManager:
    """Get or create the global JWKS manager."""
    global _jwks_manager
    if _jwks_manager is None:
        _jwks_manager = JWKSManager()
    return _jwks_manager


def init_auth():
    """Initialize authentication system. Call at application startup."""
    manager = get_jwks_manager()
    manager.start()


def verify_jwt(token: str) -> dict:
    """
    Verify a JWT token and return its payload.
    Raises appropriate exceptions on verification failure.
    """
    manager = get_jwks_manager()
    
    # Step 1: Parse JWT Header
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.exceptions.DecodeError:
        raise ValueError("Invalid token format")
    
    alg = unverified_header.get("alg")
    kid = unverified_header.get("kid")
    
    # Verify algorithm is RS256
    if alg != "RS256":
        raise ValueError("Unsupported algorithm")
    
    # Verify kid is present
    if not kid:
        raise ValueError("Missing key ID")
    
    # Step 2: Resolve Public Key
    public_key = manager.get_public_key(kid)
    if not public_key:
        # DO NOT refresh JWKS on unknown kid
        raise ValueError("Unknown key ID")
    
    # Step 3: Verify Signature
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={
                "require": ["exp", "iat", "sub"],
            }
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidSignatureError:
        raise ValueError("Invalid signature")
    except jwt.DecodeError:
        raise ValueError("Invalid token")
    
    # Step 4: Validate Claims
    # exp and iat are automatically validated by pyjwt
    
    if not payload.get("sub"):
        raise ValueError("Missing subject claim")
    
    # Ensure permissions is an array if present
    permissions = payload.get("permissions", [])
    if not isinstance(permissions, list):
        raise ValueError("Invalid permissions claim")
    
    return payload


def jwt_required(f: Callable) -> Callable:
    """
    Decorator to require JWT authentication on a Flask route.
    Sets g.user with the JWT payload on success.
    Can be disabled via DISABLE_AUTH=true environment variable.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if auth is disabled for testing
        if os.getenv("DISABLE_AUTH", "false").lower() == "true":
            # Set a mock user for testing
            g.user = {
                "sub": "test-user",
                "full_name": "Test User",
                "email": "test@example.com",
                "permissions": []
            }
            return f(*args, **kwargs)
        
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "status": "error",
                "message": "Missing or invalid Authorization header"
            }), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            payload = verify_jwt(token)
            g.user = payload
        except ValueError as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 401
        except Exception as e:
            print(f"[Auth] Unexpected error verifying JWT: {e}")
            return jsonify({
                "status": "error",
                "message": "Authentication failed"
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated


def has_permission(permission: str) -> Callable:
    """
    Decorator to require a specific permission.
    Must be used after jwt_required.
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, 'user', None)
            if not user:
                return jsonify({
                    "status": "error",
                    "message": "Authentication required"
                }), 401
            
            permissions = user.get("permissions", [])
            if permission not in permissions:
                return jsonify({
                    "status": "error",
                    "message": "Insufficient permissions"
                }), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator
