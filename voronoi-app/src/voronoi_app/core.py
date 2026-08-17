"""
Core abstractions and data structures for the Voronoi aggregation platform.

This module defines interfaces and base classes for:
- Terrain providers
- Grid generators
- Urban-form elements
- Aggregation strategies
- Space-syntax measures
- Spatial representations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple
import json
from pathlib import Path


# ============================================================================
# Schemas and Parameter Validation
# ============================================================================

@dataclass
class ParameterSchema:
    """Describes a parameter with type, range, and validation."""
    name: str
    type: str  # "float", "int", "bool", "choice"
    description: str
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[Any]] = None
    
    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Returns (is_valid, error_message)"""
        if self.type == "float":
            if not isinstance(value, (int, float)):
                return False, f"{self.name} must be numeric"
            if self.min_value is not None and value < self.min_value:
                return False, f"{self.name} must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"{self.name} must be <= {self.max_value}"
        elif self.type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                return False, f"{self.name} must be an integer"
            if self.min_value is not None and value < self.min_value:
                return False, f"{self.name} must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"{self.name} must be <= {self.max_value}"
        elif self.type == "bool":
            if not isinstance(value, bool):
                return False, f"{self.name} must be boolean"
        elif self.type == "choice":
            if self.choices and value not in self.choices:
                return False, f"{self.name} must be one of {self.choices}"
        return True, None


# ============================================================================
# Terrain Abstraction
# ============================================================================

@dataclass
class TerrainMetadata:
    """Metadata about terrain source and properties."""
    name: str
    description: str
    extent: Tuple[float, float, float, float]  # (min_x, min_y, max_x, max_y)
    units: str = "meters"
    coordinate_system: str = "local"
    source: Optional[str] = None  # e.g., "procedural", "geotiff_file.tif"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TerrainProvider(ABC):
    """Base class for all terrain generators (procedural and imported)."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this terrain provider."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ParameterSchema]:
        """Dictionary of parameter schemas keyed by parameter name."""
        pass
    
    @property
    @abstractmethod
    def metadata(self) -> TerrainMetadata:
        """Metadata about terrain extent and properties."""
        pass
    
    @abstractmethod
    def evaluate(self, x: float, y: float) -> float:
        """Evaluate elevation at coordinate (x, y)."""
        pass
    
    @abstractmethod
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return a sampled elevation field with metadata.
        
        Returns:
            Dict with keys:
            - 'elevations': 2D numpy array
            - 'x': 1D array of x coordinates
            - 'y': 1D array of y coordinates
        """
        pass
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return serializable configuration."""
        pass


# ============================================================================
# Grid Abstraction
# ============================================================================

@dataclass
class Grid:
    """Common grid representation for all grid types."""
    nodes: List[Tuple[float, float]]  # (x, y) coordinates
    edges: List[Tuple[int, int]]  # (node_i, node_j) pairs
    node_attributes: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)  # e.g., "grid_type": "voronoi"


class GridGenerator(ABC):
    """Base class for all grid generation strategies."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ParameterSchema]:
        """Dictionary of parameter schemas."""
        pass
    
    @abstractmethod
    def generate(
        self,
        terrain: TerrainProvider,
        extent: Tuple[float, float, float, float],
        seed: Optional[int] = None,
    ) -> Grid:
        """Generate a grid over the terrain extent.
        
        Args:
            terrain: TerrainProvider instance
            extent: (min_x, min_y, max_x, max_y)
            seed: Random seed for reproducibility
        
        Returns:
            Grid instance
        """
        pass
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return serializable configuration."""
        pass


# ============================================================================
# Urban Form Abstraction
# ============================================================================

@dataclass
class UrbanFormComposition:
    """Describes the composition of buildings and open spaces.
    
    For backwards compatibility, stores dyad info but can be extended
    to front yards, back yards, courtyards, circulation, etc.
    """
    type: str  # "dyad", "front_yard", "back_yard", "courtyard", etc.
    name: str  # Human-readable name
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @staticmethod
    def simple_dyad() -> "UrbanFormComposition":
        """Create a simple building + open space dyad (default)."""
        return UrbanFormComposition(
            type="dyad",
            name="Building + Open Space",
            parameters={}
        )


# ============================================================================
# Aggregation Abstraction
# ============================================================================

@dataclass
class AggregationTrace:
    """Step-by-step trace of aggregation process."""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"steps": self.steps}


@dataclass
class AggregationResult:
    """Output of aggregation strategy."""
    buildings: set  # Set of region indices
    open_spaces: set
    doors: List[Tuple[int, int]]  # (open_space, building) pairs
    building_labels: Dict[int, int]  # region -> label mapping
    trace: Optional[AggregationTrace] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class AggregationStrategy(ABC):
    """Base class for aggregation strategies."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ParameterSchema]:
        """Dictionary of parameter schemas."""
        pass
    
    @abstractmethod
    def aggregate(
        self,
        terrain: TerrainProvider,
        grid: Grid,
        form: UrbanFormComposition,
        seed: Optional[int] = None,
    ) -> AggregationResult:
        """Run aggregation strategy.
        
        Args:
            terrain: TerrainProvider instance
            grid: Grid instance
            form: UrbanFormComposition
            seed: Random seed
        
        Returns:
            AggregationResult with buildings, open spaces, doors, etc.
        """
        pass
    
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """Return serializable configuration."""
        pass


# ============================================================================
# Space-Syntax Abstraction
# ============================================================================

@dataclass
class Representation:
    """Graph-based spatial representation."""
    name: str  # "cell_graph", "dual_graph", "axial_map", etc.
    nodes: List[int]
    edges: List[Tuple[int, int]]
    node_attributes: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SpaceSyntaxMeasure(ABC):
    """Base class for space-syntax measures."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description and interpretation."""
        pass
    
    @property
    @abstractmethod
    def supported_representations(self) -> List[str]:
        """List of representation types this measure supports."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ParameterSchema]:
        """Dictionary of parameter schemas."""
        pass
    
    @abstractmethod
    def compute(
        self,
        representation: Representation,
        **kwargs
    ) -> Dict[int, float]:
        """Compute the measure for each node.
        
        Args:
            representation: Representation instance
            **kwargs: Additional parameters from self.parameters
        
        Returns:
            Dict mapping node_id -> measure_value
        """
        pass


# ============================================================================
# Urban Form Composition
# ============================================================================

@dataclass
class UrbanElement:
    """Base class for urban form elements."""
    name: str
    description: str
    parameters: Dict[str, ParameterSchema] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {k: asdict(v) for k, v in self.parameters.items()},
        }


@dataclass
class BuildingElement(UrbanElement):
    """Represents a building in urban form composition."""
    lot_size: float = 1.0  # Size relative to base cell
    frontage_ratio: float = 0.3  # Proportion on street edge
    setback: float = 0.2  # Distance from edge


@dataclass
class OpenSpaceElement(UrbanElement):
    """Represents an open space in urban form composition."""
    accessibility: float = 1.0  # 0=closed, 1=fully open
    function: str = "plaza"  # "plaza", "park", "courtyard", "street"


@dataclass
class UrbanFormComposition:
    """Composition of urban form elements for aggregation."""
    version: str = "1.0"
    name: str = "simple_dyad"
    description: str = "Simple building-open-space dyad"
    elements: List[UrbanElement] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @staticmethod
    def simple_dyad() -> "UrbanFormComposition":
        """Default: simple building-open-space pair."""
        building = BuildingElement(
            name="building",
            description="Single building unit",
            lot_size=1.0,
            frontage_ratio=0.3,
            setback=0.2,
        )
        openspace = OpenSpaceElement(
            name="open_space",
            description="Public open space",
            accessibility=1.0,
            function="plaza",
        )
        return UrbanFormComposition(
            name="simple_dyad",
            description="Simple building-open-space dyad",
            elements=[building, openspace],
        )
    
    @staticmethod
    def front_back_yards() -> "UrbanFormComposition":
        """Building with front and back yards."""
        building = BuildingElement(
            name="building",
            description="Building with yards",
            lot_size=1.0,
            frontage_ratio=0.4,
            setback=0.15,
        )
        front_yard = OpenSpaceElement(
            name="front_yard",
            description="Front-facing open space",
            accessibility=0.7,
            function="yard",
        )
        back_yard = OpenSpaceElement(
            name="back_yard",
            description="Rear-facing open space",
            accessibility=0.3,
            function="courtyard",
        )
        return UrbanFormComposition(
            name="front_back_yards",
            description="Building with front and back yards",
            elements=[building, front_yard, back_yard],
        )
    
    @staticmethod
    def courtyard_cluster() -> "UrbanFormComposition":
        """Cluster of buildings around central courtyard."""
        building = BuildingElement(
            name="building",
            description="Courtyard perimeter building",
            lot_size=0.8,
            frontage_ratio=0.5,
            setback=0.1,
        )
        courtyard = OpenSpaceElement(
            name="courtyard",
            description="Central courtyard",
            accessibility=0.2,
            function="courtyard",
        )
        street = OpenSpaceElement(
            name="street",
            description="Surrounding street",
            accessibility=1.0,
            function="street",
        )
        return UrbanFormComposition(
            name="courtyard_cluster",
            description="Building cluster around central courtyard",
            elements=[building, courtyard, street],
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "elements": [elem.to_dict() for elem in self.elements],
            "metadata": self.metadata,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "UrbanFormComposition":
        """Deserialize from dict."""
        elements = []
        for elem_dict in data.get("elements", []):
            if elem_dict.get("name") == "building":
                elem = BuildingElement(**{k: v for k, v in elem_dict.items() if k in ["name", "description", "lot_size", "frontage_ratio", "setback"]})
            else:
                elem = OpenSpaceElement(**{k: v for k, v in elem_dict.items() if k in ["name", "description", "accessibility", "function"]})
            elements.append(elem)
        
        return UrbanFormComposition(
            version=data.get("version", "1.0"),
            name=data.get("name", "custom"),
            description=data.get("description", "Custom composition"),
            elements=elements,
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# Experiment Configuration (Enhanced)
# ============================================================================

@dataclass
class ExperimentMetadata:
    """Metadata about an experiment."""
    version: str = "1.0"
    timestamp: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class ExperimentPipeline:
    """Complete pipeline configuration for an experiment."""
    version: str = "1.0"
    terrain_provider: str = "flat"  # name of terrain
    terrain_params: Dict[str, Any] = field(default_factory=dict)
    grid_generator: str = "voronoi"  # name of grid
    grid_params: Dict[str, Any] = field(default_factory=dict)
    urban_form: UrbanFormComposition = field(default_factory=UrbanFormComposition.simple_dyad)
    aggregation_strategy: str = "slope_preference"  # name of strategy
    aggregation_params: Dict[str, Any] = field(default_factory=dict)
    space_syntax_measure: str = "mean_depth"  # name of measure
    measure_params: Dict[str, Any] = field(default_factory=dict)
    representation: str = "cell_graph"  # "cell_graph", "dual_graph", etc.
    canvas_size: float = 100.0
    seed: Optional[int] = 42
    metadata: ExperimentMetadata = field(default_factory=ExperimentMetadata)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "version": self.version,
            "terrain_provider": self.terrain_provider,
            "terrain_params": self.terrain_params,
            "grid_generator": self.grid_generator,
            "grid_params": self.grid_params,
            "urban_form": self.urban_form.to_dict(),
            "aggregation_strategy": self.aggregation_strategy,
            "aggregation_params": self.aggregation_params,
            "space_syntax_measure": self.space_syntax_measure,
            "measure_params": self.measure_params,
            "representation": self.representation,
            "canvas_size": self.canvas_size,
            "seed": self.seed,
            "metadata": asdict(self.metadata),
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ExperimentPipeline":
        """Reconstruct from dict with migration support."""
        # For now, simple passthrough; will add migration logic later
        urban_form_dict = data.pop("urban_form", {})
        metadata_dict = data.pop("metadata", {})
        
        pipeline = ExperimentPipeline(**data)
        pipeline.urban_form = UrbanFormComposition(**urban_form_dict)
        pipeline.metadata = ExperimentMetadata(**metadata_dict)
        return pipeline
    
    def to_json(self, path: Path) -> None:
        """Save to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @staticmethod
    def from_json(path: Path) -> "ExperimentPipeline":
        """Load from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return ExperimentPipeline.from_dict(data)
