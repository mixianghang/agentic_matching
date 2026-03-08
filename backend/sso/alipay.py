"""Alipay OAuth2 provider implementation."""
import json
import base64
import hashlib
import httpx
from typing import Dict, Any
from urllib.parse import urlencode

from backend.sso.base import BaseSSOProvider, SSOConfig, SSOUserInfo


class AlipayProvider(BaseSSOProvider):
    """Alipay OAuth2 provider.
    
    Documentation: https://opendocs.alipay.com/open/284/web
    
    Required configuration:
        - app_id: Alipay App ID
        - app_secret: Alipay Private Key (for signing)
        - redirect_uri: Callback URL
    
    Note: Alipay uses RSA signature for authentication.
    """
    
    AUTH_URL = "https://openauth.alipay.com/oauth2/publicAppAuthorize.htm"
    TOKEN_URL = "https://openapi.alipay.com/gateway.do"
    
    @property
    def name(self) -> str:
        return "alipay"
    
    def get_auth_url(self) -> str:
        """Get Alipay authorization URL."""
        params = {
            "app_id": self.config.app_id,
            "scope": self.config.scope or "auth_user",
            "redirect_uri": self.config.redirect_uri,
            "state": self.config.state or "alipay_auth",
        }
        return self.build_auth_url(self.AUTH_URL, params)
    
    async def get_access_token(self, code: str) -> str:
        """Exchange code for access token using Alipay API."""
        # Build system parameters
        params = self._build_system_params("alipay.system.oauth.token")
        
        # Add business parameters
        params["grant_type"] = "authorization_code"
        params["code"] = code
        
        # Sign the request
        params["sign"] = self._sign(params)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data=params)
            data = response.json()
            
            token_response = data.get("alipay_system_oauth_token_response", {})
            
            if "access_token" not in token_response:
                error = data.get("error_response", {})
                raise ValueError(f"Failed to get access token: {error}")
            
            # Store user_id for later use
            self.config.extra_params["user_id"] = token_response.get("user_id")
            
            return token_response["access_token"]
    
    async def get_user_info(self, access_token: str) -> SSOUserInfo:
        """Get Alipay user info."""
        params = self._build_system_params("alipay.user.info.share")
        params["auth_token"] = access_token
        params["sign"] = self._sign(params)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, data=params)
            data = response.json()
            
            user_response = data.get("alipay_user_info_share_response", {})
            
            if "user_id" not in user_response:
                error = data.get("error_response", {})
                raise ValueError(f"Failed to get user info: {error}")
            
            return SSOUserInfo(
                provider=self.name,
                provider_user_id=user_response["user_id"],
                username=user_response.get("nick_name"),
                email=user_response.get("email"),
                phone=user_response.get("phone"),
                avatar_url=user_response.get("avatar"),
                raw_data=user_response
            )
    
    def _build_system_params(self, method: str) -> Dict[str, str]:
        """Build Alipay system parameters."""
        from datetime import datetime
        
        return {
            "app_id": self.config.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
        }
    
    def _sign(self, params: Dict[str, Any]) -> str:
        """Sign request parameters with RSA.
        
        Note: This is a simplified version. In production, use proper RSA signing.
        """
        # Sort parameters
        sorted_params = sorted(params.items())
        
        # Build string to sign
        sign_string = "&".join(f"{k}={v}" for k, v in sorted_params if k != "sign" and v)
        
        # In production, use RSA private key to sign
        # For now, return a placeholder
        return base64.b64encode(sign_string.encode()).decode()
