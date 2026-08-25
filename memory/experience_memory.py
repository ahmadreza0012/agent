"""
Experience Memory System for Self-Improving Trading Agent
Stores trading experiences and extracts lessons via vector similarity search
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not available - using in-memory fallback")


@dataclass
class Experience:
    """Single trading experience"""
    timestamp: datetime
    market_state: Dict[str, Any]  # regime, volatility, correlation, etc.
    action_taken: Dict[str, Any]  # strategy, weights, leverage
    outcome: Dict[str, Any]  # return, drawdown, sharpe
    reward: float  # objective score
    metadata: Optional[Dict] = None


class TradingMemory:
    """
    Vector database of trading experiences
    Enables quick retrieval of similar past situations
    """
    
    def __init__(self, storage_path: str = 'memory/', use_vector_db: bool = True):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.use_vector_db = use_vector_db and CHROMA_AVAILABLE
        
        if self.use_vector_db:
            settings = Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.storage_path),
                anonymized_telemetry=False
            )
            self.chroma_client = chromadb.Client(settings)
            self.collection = self.chroma_client.get_or_create_collection(
                name="trading_experiences",
                metadata={"hnsw:space": "cosine"}
            )
        else:
            self.experiences = []  # In-memory fallback
        
        logger.info(f"TradingMemory initialized (vector_db={self.use_vector_db})")
    
    def add_experience(self, exp: Experience) -> str:
        """Add new experience to memory"""
        exp_id = f"{exp.timestamp.isoformat()}"
        
        if self.use_vector_db:
            embedding_text = self._create_embedding_text(exp)
            self.collection.add(
                ids=[exp_id],
                documents=[embedding_text],
                metadatas=[{
                    'timestamp': exp.timestamp.isoformat(),
                    'reward': float(exp.reward),
                    'strategy': str(exp.action_taken.get('strategy', 'unknown')),
                    'return': float(exp.outcome.get('return', 0)),
                    'regime': str(exp.market_state.get('regime', 'unknown'))
                }],
                embeddings=None
            )
        else:
            self.experiences.append({
                'id': exp_id,
                'data': {**exp.__dict__},
                'timestamp': exp.timestamp
            })
        
        logger.info(f"Experience added: {exp_id} (reward={exp.reward:.4f})")
        return exp_id
    
    def query_similar(self, query_market_state: Dict, n_results: int = 5) -> List[Dict]:
        """Query similar past market states"""
        if not self.use_vector_db:
            sorted_exps = sorted(self.experiences, key=lambda x: x['data']['reward'], reverse=True)
            return [{'id': exp['id'], 'reward': exp['data']['reward'], 'outcome': exp['data']['outcome'], 'action': exp['data']['action_taken'], 'similarity': 1.0} for exp in sorted_exps[:n_results]]
        
        query_text = self._create_embedding_text_from_state(query_market_state)
        try:
            results = self.collection.query(query_texts=[query_text], n_results=n_results)
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({'id': results['ids'][0][i], 'document': results['documents'][0][i], 'metadata': results['metadatas'][0][i], 'distance': results['distances'][0][i] if 'distances' in results else 0})
            return formatted_results
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def extract_lessons(self, min_reward_threshold: float = 0.3) -> List[Dict]:
        """Extract high-level lessons from experiences"""
        if self.use_vector_db:
            return self._extract_lessons_chroma(min_reward_threshold)
        else:
            return self._extract_lessons_memory(min_reward_threshold)
    
    def _extract_lessons_chroma(self, min_threshold: float) -> List[Dict]:
        """Extract lessons from ChromaDB"""
        try:
            results = self.collection.get()
            if not results['ids']:
                return []
            
            lessons_by_regime = {}
            for i, exp_id in enumerate(results['ids']):
                metadata = results['metadatas'][i]
                reward = float(metadata.get('reward', 0))
                if reward < min_threshold:
                    continue
                
                regime = metadata.get('regime', 'unknown')
                strategy = metadata.get('strategy', 'unknown')
                ret = float(metadata.get('return', 0))
                
                if regime not in lessons_by_regime:
                    lessons_by_regime[regime] = {}
                if strategy not in lessons_by_regime[regime]:
                    lessons_by_regime[regime][strategy] = {'returns': [], 'count': 0, 'best_reward': 0}
                
                lessons_by_regime[regime][strategy]['returns'].append(ret)
                lessons_by_regime[regime][strategy]['count'] += 1
                lessons_by_regime[regime][strategy]['best_reward'] = max(lessons_by_regime[regime][strategy]['best_reward'], reward)
            
            lessons = []
            for regime, strategies in lessons_by_regime.items():
                best_strat = max(strategies.items(), key=lambda x: x[1]['best_reward'])[0]
                avg_return = sum(strategies[best_strat]['returns']) / len(strategies[best_strat]['returns'])
                lessons.append({'regime': regime, 'best_strategy': best_strat, 'avg_return': avg_return, 'count': strategies[best_strat]['count']})
            
            return sorted(lessons, key=lambda x: x['avg_return'], reverse=True)
        except Exception as e:
            logger.error(f"Lesson extraction failed: {e}")
            return []
    
    def _extract_lessons_memory(self, min_threshold: float) -> List[Dict]:
        """Extract lessons from in-memory storage"""
        lessons_by_regime = {}
        for exp in self.experiences:
            data = exp['data']
            if data['reward'] < min_threshold:
                continue
            
            regime = data['market_state'].get('regime', 'unknown')
            strategy = data['action_taken'].get('strategy', 'unknown')
            ret = data['outcome'].get('return', 0)
            
            if regime not in lessons_by_regime:
                lessons_by_regime[regime] = {}
            if strategy not in lessons_by_regime[regime]:
                lessons_by_regime[regime][strategy] = {'returns': [], 'count': 0}
            
            lessons_by_regime[regime][strategy]['returns'].append(ret)
            lessons_by_regime[regime][strategy]['count'] += 1
        
        lessons = []
        for regime, strategies in lessons_by_regime.items():
            for strategy, stats in strategies.items():
                avg_return = sum(stats['returns']) / len(stats['returns'])
                lessons.append({'regime': regime, 'best_strategy': strategy, 'avg_return': avg_return, 'count': stats['count']})
        
        return sorted(lessons, key=lambda x: x['avg_return'], reverse=True)
    
    def _create_embedding_text(self, exp: Experience) -> str:
        """Create text representation of experience for embedding"""
        return f"Market Regime: {exp.market_state.get('regime', 'unknown')} Volatility: {exp.market_state.get('volatility', 'unknown')} Strategy: {exp.action_taken.get('strategy', 'unknown')} Return: {exp.outcome.get('return', 0):.4f} Sharpe: {exp.outcome.get('sharpe', 0):.2f} Reward: {exp.reward:.4f}"
    
    def _create_embedding_text_from_state(self, market_state: Dict) -> str:
        """Create text representation of market state for embedding"""
        return f"Market Regime: {market_state.get('regime', 'unknown')} Volatility: {market_state.get('volatility', 'unknown')} Correlation: {market_state.get('correlation', 'unknown')}"
    
    def clear(self):
        """Clear all memories"""
        if self.use_vector_db:
            try:
                self.chroma_client.delete_collection(name="trading_experiences")
                self.collection = self.chroma_client.get_or_create_collection(name="trading_experiences", metadata={"hnsw:space": "cosine"})
            except:
                pass
        else:
            self.experiences = []
        logger.info("Memory cleared")
