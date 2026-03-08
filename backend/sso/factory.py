"""Factory for creating SSO provider instances."""
from typing import Dict, Type, Optional
import os

from backend.sso.base import BaseSSOProvider, SSOConfig
from backend.sso.wechat import WechatProvider
from backend.sso.alipay import AlipayProvider


class SSOFactory:
    """Factory for creating SSO provider instances.
    
    Usage:
        # Get WeChat provider
        provider = SSOFactory.get_provider("wechat")
        
        # Get provider with custom config
        config = SSOConfig(app_id="xxx", app_secret="yyy", redirect_uri="zzz")
        provider = SSOFactory.get_provider("wechat", config)
        
        # Register custom provider
        SSOFactory.register("custom", CustomProvider)
    
    Environment variables:
        - WECHAT_APP_ID / WECHAT_APP_SECRET
        - ALIPAY_APP_ID / ALIPAY_APP_SECRET
    """
    
    _providers: Dict[str, Type[BaseSSOProvider]] = {
        "wechat": WechatProvider,
        "alipay": AlipayProvider,
    }
    
    @classmethod
    def register(cls, name: str, provider_class: Type[BaseSSOProvider]) -> None:
        """Register a new SSO provider.
        
        Args:
            name: Provider name
            provider_class: Class inheriting from BaseSSOProvider
        """
        if not issubclass(provider_class, BaseSSOProvider):
            raise ValueError("Provider class must inherit from BaseSSOProvider")
        cls._providers[name] = provider_class
    
    @classmethod
    def get_provider(
        cls,
        name: str,
        config: Optional[SSOConfig] = None
    ) -> BaseSSOProvider:
        """Create an SSO provider instance.
        
        Args:
            name: Provider name ('wechat' or 'alipay')
            config: Optional custom configuration
            
        Returns:
            SSO provider instance
            
        Raises:
            ValueError: If provider name is unknown
        """
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider '{name}'. Available: {available}")
        
        provider_class = cls._providers[name]
        
        # Load config from environment if not provided
        if config is None:
            config = cls._load_config_from_env(name)
        
        return provider_class(config)
    
    @classmethod
    def _load_config_from_env(cls, name: str) -> SSOConfig:
        """Load provider configuration from environment variables."""
        prefix = name.upper()
        
        app_id = os.getenv(f"{prefix}_APP_ID", "")
        app_secret = os.getenv(f"{prefix}_APP_SECRET", "")
        redirect_uri = os.getenv(f"{prefix}_REDIRECT_URI", "")
        
        if not app_id or not app_secret:
            raise ValueError(
                f"Missing configuration for {name}. "
                f"Set {prefix}_APP_ID and {prefix}_APP_SECRET environment variables."
            )
        
        return SSOConfig(
            app_id=app_id,
            app_secret=app_secret,
            redirect_uri=redirect_uri
        )
    
    @classmethod
    def list_providers(cls) -> Dict[str, str]:
        """List available SSO providers.
        
        Returns:
            Dictionary mapping provider names to descriptions
        """
        return {
            name: provider_class.__doc__.split("\n")[0] if provider_class.__doc__ else "No description"
            for name, provider_class in cls._providers.items()
        }
    
    @classmethod
    def is_configured(cls, name: str) -> bool:
        """Check if a provider is properly configured.
        
        Args:
            name: Provider name
            
        Returns:
            True if configuration is complete
        """
        try:
            cls._load_config_from_env(name)
            return True
        except ValueError:
            return False
