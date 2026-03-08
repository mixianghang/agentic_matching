import pytest
from unittest.mock import Mock, patch, AsyncMock

from backend.sso import (
    BaseSSOProvider, SSOConfig, SSOUserInfo,
    WechatProvider, AlipayProvider, SSOFactory
)


class TestSSOConfig:
    """Test SSO configuration."""
    
    def test_config_creation(self):
        """Test creating SSO config."""
        config = SSOConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            redirect_uri="http://localhost/callback",
            scope="snsapi_login"
        )
        assert config.app_id == "test_app_id"
        assert config.app_secret == "test_secret"
        assert config.redirect_uri == "http://localhost/callback"
        assert config.scope == "snsapi_login"
        assert config.extra_params == {}


class TestWechatProvider:
    """Test WeChat SSO provider."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        return SSOConfig(
            app_id="wx_test_app_id",
            app_secret="test_secret",
            redirect_uri="http://localhost/callback",
            scope="snsapi_login",
            state="test_state"
        )
    
    @pytest.fixture
    def provider(self, config):
        """Create WeChat provider."""
        return WechatProvider(config)
    
    def test_name(self, provider):
        """Test provider name."""
        assert provider.name == "wechat"
    
    def test_get_auth_url(self, provider):
        """Test authorization URL generation."""
        url = provider.get_auth_url()
        assert "open.weixin.qq.com" in url
        assert "wx_test_app_id" in url
        assert "localhost" in url
        assert "callback" in url
        assert "snsapi_login" in url
        assert "test_state" in url
        assert "#wechat_redirect" in url
    
    @pytest.mark.asyncio
    async def test_get_access_token_success(self, provider):
        """Test successful token exchange."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 7200,
            "refresh_token": "refresh_token",
            "openid": "test_openid"
        }
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            token = await provider.get_access_token("test_code")
            assert token == "test_token"
    
    @pytest.mark.asyncio
    async def test_get_access_token_error(self, provider):
        """Test token exchange with error."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "errcode": 40029,
            "errmsg": "invalid code"
        }
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            with pytest.raises(ValueError) as exc_info:
                await provider.get_access_token("invalid_code")
            assert "Failed to get access token" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_user_info(self, provider):
        """Test getting user info."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "openid": "test_openid",
            "nickname": "Test User",
            "headimgurl": "http://example.com/avatar.jpg"
        }
        
        provider.config.extra_params["openid"] = "test_openid"
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            user_info = await provider.get_user_info("test_token")
            
            assert user_info.provider == "wechat"
            assert user_info.provider_user_id == "test_openid"
            assert user_info.username == "Test User"
            assert user_info.avatar_url == "http://example.com/avatar.jpg"


class TestAlipayProvider:
    """Test Alipay SSO provider."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        return SSOConfig(
            app_id="alipay_test_app_id",
            app_secret="test_private_key",
            redirect_uri="http://localhost/callback"
        )
    
    @pytest.fixture
    def provider(self, config):
        """Create Alipay provider."""
        return AlipayProvider(config)
    
    def test_name(self, provider):
        """Test provider name."""
        assert provider.name == "alipay"
    
    def test_get_auth_url(self, provider):
        """Test authorization URL generation."""
        url = provider.get_auth_url()
        assert "openauth.alipay.com" in url
        assert "alipay_test_app_id" in url
        assert "localhost" in url
        assert "callback" in url


class TestSSOFactory:
    """Test SSO Factory."""
    
    def test_get_wechat_provider(self):
        """Test getting WeChat provider."""
        config = SSOConfig(
            app_id="test_id",
            app_secret="test_secret",
            redirect_uri="http://test.com"
        )
        provider = SSOFactory.get_provider("wechat", config)
        assert isinstance(provider, WechatProvider)
    
    def test_get_alipay_provider(self):
        """Test getting Alipay provider."""
        config = SSOConfig(
            app_id="test_id",
            app_secret="test_secret",
            redirect_uri="http://test.com"
        )
        provider = SSOFactory.get_provider("alipay", config)
        assert isinstance(provider, AlipayProvider)
    
    def test_get_unknown_provider(self):
        """Test getting unknown provider raises error."""
        with pytest.raises(ValueError) as exc_info:
            SSOFactory.get_provider("unknown")
        assert "Unknown provider" in str(exc_info.value)
    
    def test_list_providers(self):
        """Test listing available providers."""
        providers = SSOFactory.list_providers()
        assert "wechat" in providers
        assert "alipay" in providers
    
    def test_register_provider(self):
        """Test registering custom provider."""
        
        class CustomProvider(BaseSSOProvider):
            @property
            def name(self):
                return "custom"
            
            def get_auth_url(self):
                return "http://custom.com"
            
            async def get_access_token(self, code):
                return "token"
            
            async def get_user_info(self, token):
                return SSOUserInfo(provider="custom", provider_user_id="123")
        
        SSOFactory.register("custom", CustomProvider)
        
        config = SSOConfig(app_id="id", app_secret="secret", redirect_uri="uri")
        provider = SSOFactory.get_provider("custom", config)
        assert isinstance(provider, CustomProvider)
