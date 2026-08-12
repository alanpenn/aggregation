from .config import ExperimentConfig
from .engine import VoronoiEngine


def run_experiment(config: ExperimentConfig):
    engine = VoronoiEngine(config)
    return engine.run()
