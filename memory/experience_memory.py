"""
Memory Module - Experience Storage and Retrieval
Stores trading experiences, lessons, and performance data
Enables self-improvement through experience replay and vector search
"""
import numpy as np
import pandas as pd
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import hashlib

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logging.warning("chromadb not available. Using simple file-based memory.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Experience:
    """Represents a single trading experience"""
    
    def __init__(self,
                 timestamp: datetime,
                 market_state: Dict,
                 action_taken: Dict,
                 outcome: Dict,
                 reward: float,
                 metadata: Dict = None):
        """
        Initialize experience record
        
        Args:
            timestamp: When experience occurred
            market_state: Market conditions (regime, prices, etc.)
            action_taken: What action was taken
            outcome: Result of the action
            reward: Numerical reward signal
            metadata: Additional context
        """
        self.timestamp = timestamp
        self.market_state = market_state
        self.action_taken = action_taken
        self.outcome = outcome
        self.reward = reward
        self.metadata = metadata or {}
        
        # Generate unique ID
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique experience ID"""
        content = f"{self.timestamp}{json.dumps(self.market_state, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'market_state': self.market_state,
            'action_taken': self.action_taken,
            'outcome': self.outcome,
            'reward': self.reward,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Experience':
        """Create from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            market_state=data['market_state'],
            action_taken=data['action_taken'],
            outcome=data['outcome'],
            reward=data['reward'],
            metadata=data.get('metadata', {})
        )


class TradingMemory:
    """
    Memory system for storing and retrieving trading experiences
    
    Features:
    - Vector storage for semantic search
    - Experience replay for learning
    - Performance tracking
    - Lesson extraction
    """
    
    def __init__(self, 
                 storage_path: str = 'memory/',
                 use_vector_db: bool = True,
                 max_experiences: int = 100000):
        """
        Initialize memory system
        
        Args:
            storage_path: Path for storing memory files
            use_vector_db: Whether to use ChromaDB for vector search
            max_experiences: Maximum experiences to store
        """
        self.storage_path = storage_path
        self.max_experiences = max_experiences
        self.use_vector_db = use_vector_db and CHROMA_AVAILABLE
        
        os.makedirs(storage_path, exist_ok=True)
        
        # In-memory experience buffer
        self.experiences: List[Experience] = []
        
        # Performance history
        self.performance_history = []
        
        # Lessons learned
        self.lessons = []
        
        # Initialize vector DB if available
        if self.use_vector_db:
            self._init_chromadb()
        else:
            self.client = None
            logger.info("Using file-based memory (ChromaDB not available)")
        
        # Load existing memories
        self._load_memories()
        
        logger.info(f"TradingMemory initialized: {len(self.experiences)} experiences loaded")
    
    def _init_chromadb(self):
        """Initialize ChromaDB for vector storage"""
        try:
            self.client = chromadb.PersistentClient(
                path=os.path.join(self.storage_path, 'chroma_db')
            )
            
            # Create collection
            self.collection = self.client.get_or_create_collection(
                name='trading_experiences',
                metadata={"description": "Trading experiences for RL agent"}
            )
            
            logger.info("ChromaDB initialized successfully")
            
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
            self.use_vector_db = False
            self.client = None
    
    def add_experience(self, experience: Experience):
        """
        Add new experience to memory
        
        Args:
            experience: Experience object to store
        """
        # Add to in-memory buffer
        self.experiences.append(experience)
        
        # Trim if exceeds max
        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences:]
        
        # Store in vector DB
        if self.use_vector_db and self.client:
            try:
                # Create embedding text
                embedding_text = self._experience_to_text(experience)
                
                # Add to collection
                self.collection.add(
                    documents=[embedding_text],
                    metadatas=[{
                        'reward': experience.reward,
                        'timestamp': experience.timestamp.isoformat(),
                        'regime': experience.market_state.get('regime', 'unknown')
                    }],
                    ids=[experience.id]
                )
            except Exception as e:
                logger.error(f"Error adding to ChromaDB: {e}")
        
        # Save periodically
        if len(self.experiences) % 100 == 0:
            self._save_memories()
    
    def _experience_to_text(self, experience: Experience) -> str:
        """Convert experience to text for embedding"""
        text = f"""
        Market State: regime={experience.market_state.get('regime', 'N/A')}, 
        volatility={experience.market_state.get('volatility', 'N/A')}
        
        Action: strategy={experience.action_taken.get('strategy', 'N/A')},
        weights={experience.action_taken.get('weights', 'N/A')}
        
        Outcome: return={experience.outcome.get('return', 'N/A')},
        drawdown={experience.outcome.get('drawdown', 'N/A')}
        
        Reward: {experience.reward}
        """
        return text.strip()
    
    def search_similar_experiences(self,
                                   query_market_state: Dict,
                                   n_results: int = 10,
                                   min_reward: float = None) -> List[Experience]:
        """
        Search for similar past experiences
        
        Args:
            query_market_state: Current market state to match
            n_results: Number of results to return
            min_reward: Filter for experiences with at least this reward
            
        Returns:
            List of similar experiences
        """
        if not self.use_vector_db or not self.client:
            # Fallback: simple filtering
            return self._simple_search(query_market_state, n_results, min_reward)
        
        try:
            # Create query text
            query_text = f"""
            Market State: regime={query_market_state.get('regime', 'N/A')},
            volatility={query_market_state.get('volatility', 'N/A')}
            """
            
            # Search
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={'reward': {'$gte': min_reward}} if min_reward else None
            )
            
            # Convert to experiences (simplified - would need full reconstruction)
            similar = []
            if results and results['metadatas']:
                for meta in results['metadatas'][0]:
                    exp = Experience(
                        timestamp=datetime.fromisoformat(meta['timestamp']),
                        market_state={'regime': meta.get('regime', 'unknown')},
                        action_taken={},
                        outcome={},
                        reward=meta.get('reward', 0)
                    )
                    similar.append(exp)
            
            return similar
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return self._simple_search(query_market_state, n_results, min_reward)
    
    def _simple_search(self,
                       query_market_state: Dict,
                       n_results: int,
                       min_reward: float) -> List[Experience]:
        """Simple fallback search without vector DB"""
        # Filter by regime if specified
        query_regime = query_market_state.get('regime')
        
        filtered = self.experiences
        if query_regime:
            filtered = [
                e for e in filtered 
                if e.market_state.get('regime') == query_regime
            ]
        
        # Filter by minimum reward
        if min_reward is not None:
            filtered = [e for e in filtered if e.reward >= min_reward]
        
        # Sort by reward (descending)
        filtered.sort(key=lambda x: x.reward, reverse=True)
        
        return filtered[:n_results]
    
    def get_best_experiences(self,
                             regime: str = None,
                             n_results: int = 20) -> List[Experience]:
        """
        Get best performing experiences
        
        Args:
            regime: Filter by regime
            n_results: Number to return
            
        Returns:
            Top experiences by reward
        """
        if regime:
            filtered = [
                e for e in self.experiences 
                if e.market_state.get('regime') == regime
            ]
        else:
            filtered = self.experiences
        
        # Sort by reward
        filtered.sort(key=lambda x: x.reward, reverse=True)
        
        return filtered[:n_results]
    
    def extract_lessons(self, min_reward_threshold: float = 0.5) -> List[Dict]:
        """
        Extract lessons from high-reward experiences
        
        Args:
            min_reward_threshold: Minimum reward to consider
            
        Returns:
            List of lesson dictionaries
        """
        high_reward = [
            e for e in self.experiences 
            if e.reward >= min_reward_threshold
        ]
        
        lessons = []
        
        # Group by regime
        by_regime = {}
        for exp in high_reward:
            regime = exp.market_state.get('regime', 'unknown')
            if regime not in by_regime:
                by_regime[regime] = []
            by_regime[regime].append(exp)
        
        # Extract patterns
        for regime, experiences in by_regime.items():
            if len(experiences) < 3:
                continue
            
            # Find common strategies
            strategies = [e.action_taken.get('strategy') for e in experiences]
            most_common_strategy = max(set(strategies), key=strategies.count)
            
            # Average outcome
            avg_return = np.mean([e.outcome.get('return', 0) for e in experiences])
            avg_drawdown = np.mean([e.outcome.get('drawdown', 0) for e in experiences])
            
            lesson = {
                'regime': regime,
                'best_strategy': most_common_strategy,
                'avg_return': avg_return,
                'avg_drawdown': avg_drawdown,
                'sample_size': len(experiences),
                'confidence': 'high' if len(experiences) > 10 else 'medium',
                'extracted_at': datetime.now().isoformat()
            }
            
            lessons.append(lesson)
            self.lessons.append(lesson)
        
        logger.info(f"Extracted {len(lessons)} lessons from experience")
        return lessons
    
    def record_performance(self, metrics: Dict):
        """
        Record trading performance metrics
        
        Args:
            metrics: Performance metrics dictionary
        """
        record = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics
        }
        
        self.performance_history.append(record)
        
        # Keep last 1000 records
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
    
    def get_performance_trend(self, window: int = 100) -> pd.DataFrame:
        """
        Get recent performance trend
        
        Args:
            window: Number of records to analyze
            
        Returns:
            DataFrame with performance metrics
        """
        if len(self.performance_history) < 2:
            return pd.DataFrame()
        
        recent = self.performance_history[-window:]
        
        df = pd.DataFrame([r['metrics'] for r in recent])
        df['timestamp'] = [r['timestamp'] for r in recent]
        
        return df
    
    def _save_memories(self):
        """Save memories to disk"""
        try:
            # Save experiences
            exp_file = os.path.join(self.storage_path, 'experiences.json')
            data = [e.to_dict() for e in self.experiences]
            with open(exp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Save lessons
            lesson_file = os.path.join(self.storage_path, 'lessons.json')
            with open(lesson_file, 'w') as f:
                json.dump(self.lessons, f, indent=2)
            
            # Save performance history
            perf_file = os.path.join(self.storage_path, 'performance.json')
            with open(perf_file, 'w') as f:
                json.dump(self.performance_history, f, indent=2)
            
            logger.info(f"Memories saved: {len(self.experiences)} experiences")
            
        except Exception as e:
            logger.error(f"Error saving memories: {e}")
    
    def _load_memories(self):
        """Load memories from disk"""
        try:
            # Load experiences
            exp_file = os.path.join(self.storage_path, 'experiences.json')
            if os.path.exists(exp_file):
                with open(exp_file, 'r') as f:
                    data = json.load(f)
                self.experiences = [Experience.from_dict(d) for d in data]
            
            # Load lessons
            lesson_file = os.path.join(self.storage_path, 'lessons.json')
            if os.path.exists(lesson_file):
                with open(lesson_file, 'r') as f:
                    self.lessons = json.load(f)
            
            # Load performance history
            perf_file = os.path.join(self.storage_path, 'performance.json')
            if os.path.exists(perf_file):
                with open(perf_file, 'r') as f:
                    self.performance_history = json.load(f)
            
            logger.info(f"Loaded {len(self.experiences)} experiences from disk")
            
        except Exception as e:
            logger.error(f"Error loading memories: {e}")
    
    def clear_memories(self):
        """Clear all stored memories"""
        self.experiences = []
        self.lessons = []
        self.performance_history = []
        
        if self.use_vector_db and self.client:
            try:
                self.client.delete_collection('trading_experiences')
                self.collection = self.client.create_collection('trading_experiences')
            except Exception as e:
                logger.error(f"Error clearing ChromaDB: {e}")
        
        logger.info("All memories cleared")


if __name__ == "__main__":
    # Test memory system
    memory = TradingMemory(storage_path='test_memory/', use_vector_db=False)
    
    # Add some test experiences
    for i in range(50):
        exp = Experience(
            timestamp=datetime.now(),
            market_state={
                'regime': np.random.choice(['Bull', 'Bear', 'Sideways']),
                'volatility': np.random.uniform(0.01, 0.05)
            },
            action_taken={
                'strategy': np.random.choice(['momentum', 'risk_parity', 'mean_reversion']),
                'weights': [0.2, 0.2, 0.2, 0.2, 0.2]
            },
            outcome={
                'return': np.random.uniform(-0.1, 0.2),
                'drawdown': np.random.uniform(-0.15, 0)
            },
            reward=np.random.uniform(-1, 2)
        )
        memory.add_experience(exp)
    
    print(f"\n=== Memory Test ===")
    print(f"Total experiences: {len(memory.experiences)}")
    
    # Search for similar experiences
    query_state = {'regime': 'Bull', 'volatility': 0.02}
    similar = memory.search_similar_experiences(query_state, n_results=5)
    print(f"\nSimilar experiences to {query_state}: {len(similar)}")
    
    # Get best experiences
    best = memory.get_best_experiences(n_results=5)
    print(f"\nBest experiences (top 5):")
    for exp in best:
        print(f"  Reward: {exp.reward:.3f}, Regime: {exp.market_state.get('regime')}")
    
    # Extract lessons
    lessons = memory.extract_lessons(min_reward_threshold=0.5)
    print(f"\nExtracted lessons: {len(lessons)}")
    for lesson in lessons:
        print(f"  Regime: {lesson['regime']}, Best Strategy: {lesson['best_strategy']}")
    
    # Save
    memory._save_memories()
    print("\nMemories saved successfully")
