import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging
logger = logging.getLogger(__name__)

@dataclass
class ModelMetadata:
    version_id: str; created_at: datetime; training_start: datetime; training_end: datetime
    feature_version: str; hyperparameters: Dict[str, Any]; training_metrics: Dict[str, float]
    validation_metrics: Dict[str, float]; oos_metrics: Optional[Dict[str, float]] = None
    model_type: str = 'random_forest'; status: str = 'experimental'
    def to_dict(self) -> Dict:
        d = asdict(self)
        for k in ['created_at', 'training_start', 'training_end']:
            d[k] = d[k].isoformat()
        return d

class ModelRegistry:
    def __init__(self): self._models: Dict[str, ModelMetadata] = {}; self._next_id = 0
    def register_model(self, model: Any, metadata: Dict[str, Any]) -> str:
        self._next_id += 1; vid = f"v{self._next_id:04d}"
        mm = ModelMetadata(version_id=vid, created_at=datetime.now(), training_start=metadata.get('training_start', datetime.now()), training_end=metadata.get('training_end', datetime.now()), feature_version=metadata.get('feature_version', 'v1'), hyperparameters=metadata.get('hyperparameters', {}), training_metrics=metadata.get('training_metrics', {}), validation_metrics=metadata.get('validation_metrics', {}), oos_metrics=metadata.get('oos_metrics'), model_type=metadata.get('model_type', 'random_forest'), status=metadata.get('status', 'experimental'))
        self._models[vid] = mm; return vid
    def get_model(self, version_id: str) -> Optional[ModelMetadata]: return self._models.get(version_id)
    def get_best_model(self, metric: str = 'sharpe_oos') -> Optional[ModelMetadata]:
        valid = [m for m in self._models.values() if m.oos_metrics and metric in m.oos_metrics]
        return max(valid, key=lambda m: m.oos_metrics.get(metric, -float('inf'))) if valid else None
    def list_models(self) -> List[str]: return list(self._models.keys())
