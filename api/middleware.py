"""
API Middleware - Logging, rate limiting, authentication.
"""

import os
import time
import uuid
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        start_time = time.time()
        
        logger.info(f"REQUEST {request_id} | {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"RESPONSE {request_id} | {response.status_code} | "
                f"{duration:.2f}ms"
            )
            return response
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"ERROR {request_id} | {e} | {duration:.2f}ms")
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting by IP."""
    
    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self._requests: Dict[str, List[float]] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean old requests
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if now - t < 60
        ]
        
        if len(self._requests[client_ip]) >= self.calls_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        self._requests[client_ip].append(now)
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication."""
    
    def __init__(self, app, excluded_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or []
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Check API key for write operations
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing API key"}
                )
            # Validate API key from environment
            expected_key = os.getenv("API_KEY", "test-key")
            if api_key != expected_key:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid API key"}
                )
        
        return await call_next(request)
