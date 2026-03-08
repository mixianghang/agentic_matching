"""Base class for task matching algorithms."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.models import Task


@dataclass
class MatchResult:
    """Result of a task match."""
    task_id: str
    score: float  # 0.0 to 1.0
    matched_task_id: str
    matched_task: Optional[Task] = None
    reason: str = ""
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now()


class BaseMatcher(ABC):
    """Abstract base class for task matching algorithms.
    
    To implement a new matching algorithm:
    1. Create a new class inheriting from BaseMatcher
    2. Implement the `match` method
    3. Register it in the MatcherFactory
    
    Example:
        class MyMatcher(BaseMatcher):
            def match(self, task: Task, candidate_tasks: List[Task]) -> List[MatchResult]:
                # Your matching logic here
                return results
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize matcher with configuration.
        
        Args:
            config: Dictionary containing matcher-specific configuration
        """
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def match(self, task: Task, candidate_tasks: List[Task]) -> List[MatchResult]:
        """Find matching tasks for a given task.
        
        Args:
            task: The task to find matches for
            candidate_tasks: List of potential matching tasks
            
        Returns:
            List of MatchResult objects sorted by score (descending)
        """
        pass
    
    def filter_candidates(self, task: Task, candidate_tasks: List[Task]) -> List[Task]:
        """Filter candidate tasks before matching.
        
        Override this method to implement custom filtering logic.
        Default implementation filters by:
        - Same task type
        - Different user
        - Active status
        
        Args:
            task: The task to find matches for
            candidate_tasks: List of all candidate tasks
            
        Returns:
            Filtered list of candidate tasks
        """
        return [
            t for t in candidate_tasks
            if t.task_type == task.task_type
            and t.user_id != task.user_id
            and t.status in ["pending", "active"]
            and t.id != task.id
        ]
    
    def calculate_score(self, task1: Task, task2: Task) -> float:
        """Calculate match score between two tasks.
        
        Override this method to implement custom scoring logic.
        
        Args:
            task1: First task
            task2: Second task
            
        Returns:
            Match score between 0.0 and 1.0
        """
        return 0.5  # Default neutral score
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
