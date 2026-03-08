import pytest
from backend.matching import BaseMatcher, MatchResult, SimpleMatcher, MatcherFactory
from backend.models import Task, TaskStatus


class TestMatchResult:
    """Test MatchResult dataclass."""
    
    def test_match_result_creation(self):
        """Test creating a MatchResult."""
        result = MatchResult(
            task_id="task1",
            score=0.85,
            matched_task_id="task2",
            reason="Good match"
        )
        assert result.task_id == "task1"
        assert result.score == 0.85
        assert result.matched_task_id == "task2"
        assert result.reason == "Good match"
        assert result.metadata == {}
        assert result.created_at is not None


class TestSimpleMatcher:
    """Test SimpleMatcher implementation."""
    
    @pytest.fixture
    def matcher(self):
        """Create a SimpleMatcher instance."""
        return SimpleMatcher({
            "min_score": 0.3,
            "max_results": 5,
            "description_weight": 0.6,
            "requirements_weight": 0.4
        })
    
    @pytest.fixture
    def sample_task(self):
        """Create a sample task."""
        return Task(
            id="task1",
            user_id="user1",
            agent_id="agent1",
            task_type="dating",
            description="Looking for a partner who likes hiking",
            requirements={"age": 25, "location": "Beijing"},
            status=TaskStatus.PENDING
        )
    
    @pytest.fixture
    def candidate_tasks(self):
        """Create sample candidate tasks."""
        return [
            Task(
                id="task2",
                user_id="user2",
                agent_id="agent2",
                task_type="dating",
                description="Love hiking and outdoor activities",
                requirements={"age": 26, "location": "Beijing"},
                status=TaskStatus.PENDING
            ),
            Task(
                id="task3",
                user_id="user3",
                agent_id="agent3",
                task_type="dating",
                description="Enjoy reading books",
                requirements={"age": 30, "location": "Shanghai"},
                status=TaskStatus.PENDING
            ),
            Task(
                id="task4",
                user_id="user4",
                agent_id="agent4",
                task_type="rental",  # Different type
                description="Looking for hiking partner",
                requirements={},
                status=TaskStatus.PENDING
            ),
        ]
    
    def test_filter_candidates(self, matcher, sample_task, candidate_tasks):
        """Test candidate filtering."""
        filtered = matcher.filter_candidates(sample_task, candidate_tasks)
        
        # Should filter out different type and same user
        assert len(filtered) == 2
        assert all(t.task_type == "dating" for t in filtered)
        assert all(t.user_id != "user1" for t in filtered)
    
    def test_description_similarity(self, matcher):
        """Test description similarity calculation."""
        desc1 = "I love hiking and reading"
        desc2 = "I enjoy hiking and books"
        
        similarity = matcher._description_similarity(desc1, desc2)
        assert 0 < similarity < 1
        
        # Same description should have similarity 1
        assert matcher._description_similarity(desc1, desc1) == 1.0
        
        # Completely different should have low similarity
        desc3 = "xyz abc def"
        assert matcher._description_similarity(desc1, desc3) < 0.5
    
    def test_requirements_match_score(self, matcher):
        """Test requirements matching."""
        req1 = {"age": 25, "location": "Beijing"}
        req2 = {"age": 25, "location": "Beijing"}
        
        score = matcher._requirements_match_score(req1, req2)
        assert score == 1.0
        
        # Partial match
        req3 = {"age": 30, "location": "Beijing"}
        score = matcher._requirements_match_score(req1, req3)
        assert 0 < score < 1
    
    def test_match(self, matcher, sample_task, candidate_tasks):
        """Test matching algorithm."""
        results = matcher.match(sample_task, candidate_tasks)
        
        # Should return results
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Results should be sorted by score
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score
        
        # All results should have required fields
        for result in results:
            assert result.task_id == "task1"
            assert result.score >= matcher.min_score
            assert result.matched_task is not None
            assert result.reason != ""


class TestMatcherFactory:
    """Test MatcherFactory."""
    
    def test_get_simple_matcher(self):
        """Test getting simple matcher."""
        matcher = MatcherFactory.get_matcher("simple")
        assert isinstance(matcher, SimpleMatcher)
    
    def test_get_matcher_with_config(self):
        """Test getting matcher with configuration."""
        config = {"min_score": 0.5, "max_results": 3}
        matcher = MatcherFactory.get_matcher("simple", config)
        
        assert matcher.min_score == 0.5
        assert matcher.max_results == 3
    
    def test_get_default_matcher(self):
        """Test getting default matcher."""
        matcher = MatcherFactory.get_matcher()
        assert isinstance(matcher, SimpleMatcher)
    
    def test_list_matchers(self):
        """Test listing available matchers."""
        matchers = MatcherFactory.list_matchers()
        assert "simple" in matchers
    
    def test_register_matcher(self):
        """Test registering custom matcher."""
        
        class CustomMatcher(BaseMatcher):
            """Custom matcher for testing."""
            
            def match(self, task, candidate_tasks):
                return []
        
        MatcherFactory.register("custom", CustomMatcher)
        
        matcher = MatcherFactory.get_matcher("custom")
        assert isinstance(matcher, CustomMatcher)
    
    def test_get_unknown_matcher(self):
        """Test getting unknown matcher raises error."""
        with pytest.raises(ValueError) as exc_info:
            MatcherFactory.get_matcher("unknown")
        
        assert "Unknown matcher" in str(exc_info.value)
