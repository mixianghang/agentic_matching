"""WeChat OAuth2 provider implementation."""
import httpx
from typing import Dict, Any

from backend.sso.base import BaseSSOProvider, SSOConfig, SSOUserInfo


class WechatProvider(BaseSSOProvider):
    """WeChat OAuth2 provider.
    
    Documentation: https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html
    
    Required configuration:
        - app_id: WeChat App ID
        - app_secret: WeChat App Secret
        - redirect_uri: Callback URL
    
    Optional configuration:
        - scope: Authorization scope (default: 'snsapi_login')
    """
    
    AUTH_URL = "https://open.weixin.qq.com/connect/qrconnect"
    TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
    USER_INFO_URL = "https://api.weixin.qq.com/sns/userinfo"
    
    @property
    def name(self) -> str:
        return "wechat"
    
    def get_auth_url(self) -> str:
        """Get WeChat authorization URL."""
        params = {
            "appid": self.config.app_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.config.scope or "snsapi_login",
            "state": self.config.state or "wechat_auth",
        }
        # WeChat uses #wechat_redirect anchor
        auth_url = self.build_auth_url(self.AUTH_URL, params)
        return f"{auth_url}#wechat_redirect"
    
    async def get_access_token(self, code: str) -> str:
        """Exchange code for access token."""
        params = {
            "appid": self.config.app_id,
            "secret": self.config.app_secret,
            "code": code,
            "grant_type": "authorization_code",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.TOKEN_URL, params=params)
            data = response.json()
            
            if "access_token" not in data:
                error_msg = data.get("errmsg", "Unknown error")
                raise ValueError(f"Failed to get access token: {error_msg}")
            
            return data["access_token"]
    
    async def get_user_info(self, access_token: str) -> SSOUserInfo:
        """Get WeChat user info."""
        # First, get OpenID
        params = {
            "access_token": access_token,
        }
        
        async with httpx.AsyncClient() as client:
            # Get user info
            user_params = {
                "access_token": access_token,
                "openid": self.config.extra_params.get("openid", ""),
            }
            
            response = await client.get(self.USER_INFO_URL, params=user_params)
            data = response.json()
            
            if "openid" not in data:
                error_msg = data.get("errmsg", "Unknown error")
                raise ValueError(f"Failed to get user info: {error_msg}")
            
            return SSOUserInfo(
                provider=self.name,
                provider_user_id=data["openid"],
                username=data.get("nickname"),
                avatar_url=data.get("headimgurl"),
                raw_data=data
            )
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token.
        
        Args:
            refresh_token: Refresh token from initial authorization
            
        Returns:
            New token data
        """
        url = "https://api.weixin.qq.com/sns/oauth2/refresh_token"
        params = {
            "appid": self.config.app_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            return response.json()
