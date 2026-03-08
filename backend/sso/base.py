"""Base class for SSO providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from urllib.parse import urlencode


@dataclass
class SSOConfig:
    """Configuration for SSO provider."""
    app_id: str
    app_secret: str
    redirect_uri: str
    scope: str = ""
    state: str = ""
    
    # Optional additional config
    extra_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


@dataclass
class SSOUserInfo:
    """User information from SSO provider."""
    provider: str
    provider_user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.raw_data is None:
            self.raw_data = {}


class BaseSSOProvider(ABC):
    """Abstract base class for SSO providers.
    
    To implement a new SSO provider:
    1. Create a new class inheriting from BaseSSOProvider
    2. Implement all abstract methods
    3. Register it in the SSOFactory
    
    Example:
        class MySSOProvider(BaseSSOProvider):
            @property
            def name(self) -> str:
                return "my_sso"
            
            def get_auth_url(self) -> str:
                # Build and return authorization URL
                pass
            
            async def get_access_token(self, code: str) -> str:
                # Exchange code for access token
                pass
            
            async def get_user_info(self, access_token: str) -> SSOUserInfo:
                # Fetch user info using access token
                pass
    """
    
    def __init__(self, config: SSOConfig):
        """Initialize SSO provider with configuration.
        
        Args:
            config: SSO configuration
        """
        self.config = config
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name."""
        pass
    
    @abstractmethod
    def get_auth_url(self) -> str:
        """Get authorization URL for initiating OAuth flow.
        
        Returns:
            Full authorization URL
        """
        pass
    
    @abstractmethod
    async def get_access_token(self, code: str) -> str:
        """Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Access token
        """
        pass
    
    @abstractmethod
    async def get_user_info(self, access_token: str) -> SSOUserInfo:
        """Get user information using access token.
        
        Args:
            access_token: Valid access token
            
        Returns:
            User information
        """
        pass
    
    def build_auth_url(self, base_url: str, params: Dict[str, str]) -> str:
        """Helper method to build authorization URL.
        
        Args:
            base_url: Base authorization endpoint
            params: URL parameters
            
        Returns:
            Full URL with query parameters
        """
        return f"{base_url}?{urlencode(params)}"
