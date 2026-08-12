from dataclasses import dataclass
from typing import Optional


@dataclass
class ExperimentConfig:
    num_points: int = 500
    canvas_size: float = 100.0
    slope_preference: float = 0.95
    max_dyads: int = 100
    stagnation_limit: int = 1000
    seed: Optional[int] = 42

    def validate(self) -> None:
        if not 0 <= self.slope_preference <= 1:
            raise ValueError("slope_preference must be between 0 and 1")
        if self.num_points < 10:
            raise ValueError("num_points must be at least 10")
        if self.max_dyads < 1:
            raise ValueError("max_dyads must be at least 1")
        if self.stagnation_limit < 1:
            raise ValueError("stagnation_limit must be at least 1")
