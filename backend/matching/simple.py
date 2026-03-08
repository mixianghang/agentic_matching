"""Simple matching algorithm implementation."""
import json
from typing import List, Dict, Any
from difflib import SequenceMatcher

from backend.models import Task
from backend.matching.base import BaseMatcher, MatchResult


class SimpleMatcher(BaseMatcher):
    """Simple keyword-based matching algorithm.
    
    This matcher uses:
    1. Task type matching (exact match required)
    2. Keyword overlap in description
    3. Requirements compatibility
    
    Configuration options:
        - min_score: Minimum match score threshold (default: 0.3)
        - max_results: Maximum number of results to return (default: 10)
        - description_weight: Weight for description similarity (default: 0.6)
        - requirements_weight: Weight for requirements compatibility (default: 0.4)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.min_score = self.get_config("min_score", 0.3)
        self.max_results = self.get_config("max_results", 10)
        self.description_weight = self.get_config("description_weight", 0.6)
        self.requirements_weight = self.get_config("requirements_weight", 0.4)
    
    def match(self, task: Task, candidate_tasks: List[Task]) -> List[MatchResult]:
        """Find matching tasks using simple algorithm."""
        # Filter candidates
        filtered = self.filter_candidates(task, candidate_tasks)
        
        # Calculate scores
        results = []
        for candidate in filtered:
            score = self.calculate_score(task, candidate)
            if score >= self.min_score:
                results.append(MatchResult(
                    task_id=task.id,
                    score=score,
                    matched_task_id=candidate.id,
                    matched_task=candidate,
                    reason=self._generate_reason(task, candidate, score),
                    metadata={
                        "description_similarity": self._description_similarity(
                            task.description, candidate.description
                        ),
                        "requirements_match": self._requirements_match_score(
                            task.requirements, candidate.requirements
                        )
                    }
                ))
        
        # Sort by score descending and limit results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:self.max_results]
    
    def calculate_score(self, task1: Task, task2: Task) -> float:
        """Calculate match score between two tasks."""
        # Description similarity
        desc_score = self._description_similarity(
            task1.description, task2.description
        )
        
        # Requirements compatibility
        req_score = self._requirements_match_score(
            task1.requirements, task2.requirements
        )
        
        # Weighted combination
        total_score = (
            self.description_weight * desc_score +
            self.requirements_weight * req_score
        )
        
        return min(1.0, max(0.0, total_score))
    
    def _description_similarity(self, desc1: str, desc2: str) -> float:
        """Calculate text similarity between descriptions."""
        # Convert to lowercase and split into words
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard similarity
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _requirements_match_score(
        self, req1: Dict[str, Any], req2: Dict[str, Any]
    ) -> float:
        """Calculate requirements compatibility score."""
        if not req1 or not req2:
            return 0.5  # Neutral if no requirements
        
        # Find common keys
        common_keys = set(req1.keys()) & set(req2.keys())
        if not common_keys:
            return 0.5  # Neutral if no common requirements
        
        matches = 0
        for key in common_keys:
            val1 = req1[key]
            val2 = req2[key]
            
            # Exact match
            if val1 == val2:
                matches += 1
            # Numeric range overlap (simplified)
            elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                # Consider values within 20% as matching
                if max(val1, val2) > 0:
                    diff = abs(val1 - val2) / max(val1, val2)
                    if diff < 0.2:
                        matches += 0.5
        
        return matches / len(common_keys)
    
    def _generate_reason(self, task: Task, candidate: Task, score: float) -> str:
        """Generate human-readable match reason."""
        if score > 0.8:
            return "高度匹配：任务类型和需求非常相似"
        elif score > 0.6:
            return "较好匹配：有共同的需求和兴趣"
        elif score > 0.4:
            return "一般匹配：部分需求相符"
        else:
            return "潜在匹配：可以尝试联系"
