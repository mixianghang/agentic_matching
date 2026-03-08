"""Factory for creating matcher instances."""
from typing import Dict, Type, Any, Optional
import os

from backend.matching.base import BaseMatcher
from backend.matching.simple import SimpleMatcher


class MatcherFactory:
    """Factory for creating task matcher instances.
    
    Usage:
        # Get default matcher
        matcher = MatcherFactory.get_matcher()
        
        # Get specific matcher with config
        matcher = MatcherFactory.get_matcher("simple", {"min_score": 0.5})
        
        # Register custom matcher
        MatcherFactory.register("my_matcher", MyMatcherClass)
    """
    
    _matchers: Dict[str, Type[BaseMatcher]] = {
        "simple": SimpleMatcher,
    }
    
    _default_matcher: str = "simple"
    
    @classmethod
    def register(cls, name: str, matcher_class: Type[BaseMatcher]) -> None:
        """Register a new matcher class.
        
        Args:
            name: Unique name for the matcher
            matcher_class: Class inheriting from BaseMatcher
        """
        if not issubclass(matcher_class, BaseMatcher):
            raise ValueError(f"Matcher class must inherit from BaseMatcher")
        cls._matchers[name] = matcher_class
    
    @classmethod
    def get_matcher(
        cls,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> BaseMatcher:
        """Create a matcher instance.
        
        Args:
            name: Matcher name (defaults to environment variable MATCHER_TYPE or 'simple')
            config: Configuration dictionary for the matcher
            
        Returns:
            Matcher instance
            
        Raises:
            ValueError: If matcher name is not registered
        """
        # Get matcher name from parameter, environment, or default
        if name is None:
            name = os.getenv("MATCHER_TYPE", cls._default_matcher)
        
        if name not in cls._matchers:
            available = ", ".join(cls._matchers.keys())
            raise ValueError(
                f"Unknown matcher '{name}'. Available: {available}"
            )
        
        matcher_class = cls._matchers[name]
        return matcher_class(config)
    
    @classmethod
    def list_matchers(cls) -> Dict[str, str]:
        """List all available matchers.
        
        Returns:
            Dictionary mapping matcher names to descriptions
        """
        return {
            name: matcher_class.__doc__.split("\n")[0] if matcher_class.__doc__ else "No description"
            for name, matcher_class in cls._matchers.items()
        }
    
    @classmethod
    def set_default(cls, name: str) -> None:
        """Set the default matcher.
        
        Args:
            name: Name of the matcher to set as default
        """
        if name not in cls._matchers:
            raise ValueError(f"Unknown matcher '{name}'")
        cls._default_matcher = name
