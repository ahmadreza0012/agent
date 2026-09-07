import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Iterator
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

@dataclass
class FoldResult:
    fold_idx: int; train_start: int; train_end: int; test_start: int; test_end: int
    train_indices: np.ndarray; test_indices: np.ndarray; gap: int; purge: int

class PurgedWalkForwardValidator:
    def __init__(self, n_splits=5, test_size=0.1, gap=10, purge=20, min_train_size=100):
        self.n_splits = n_splits; self.test_size = test_size; self.gap = gap; self.purge = purge; self.min_train_size = min_train_size
    
    def split(self, X: pd.DataFrame, y=None, groups=None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        n_samples = len(X)
        test_size = int(n_samples * self.test_size) if isinstance(self.test_size, float) else self.test_size
        min_train = int(n_samples * self.min_train_size) if isinstance(self.min_train_size, float) else self.min_train_size
        
        total_per_fold = self.gap + test_size + self.purge
        available = n_samples - min_train
        n_actual = min(self.n_splits, max(1, available // total_per_fold))
        step = max(1, (available - total_per_fold) // (n_actual - 1)) if n_actual > 1 else 0
        
        for i in range(n_actual):
            test_start = min_train + self.gap + i * step
            test_end = test_start + test_size
            train_start = 0 if i == 0 else (min_train + self.gap + (i-1)*step + test_size + self.purge)
            train_end = test_start - self.gap
            if train_end <= train_start or test_end > n_samples: continue
            train_idx = np.arange(train_start, min(train_end, n_samples))
            test_idx = np.arange(test_start, min(test_end, n_samples))
            if len(train_idx) == 0 or len(test_idx) == 0: continue
            if len(set(train_idx) & set(test_idx)) == 0:
                yield train_idx, test_idx

class LookaheadError(Exception): pass
