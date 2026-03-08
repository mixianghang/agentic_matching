"""Third-party SSO authentication package."""
from .base import BaseSSOProvider, SSOConfig, SSOUserInfo
from .wechat import WechatProvider
from .alipay import AlipayProvider
from .factory import SSOFactory

__all__ = ["BaseSSOProvider", "SSOConfig", "SSOUserInfo", "WechatProvider", "AlipayProvider", "SSOFactory"]
