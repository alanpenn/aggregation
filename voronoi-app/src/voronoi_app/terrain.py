"""
Terrain provider implementations.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
from .core import TerrainProvider, TerrainMetadata, ParameterSchema


class FlatTerrainProvider(TerrainProvider):
    """Flat terrain at elevation 0."""
    
    def __init__(self):
        self._extent: Tuple[float, float, float, float] = (0, 0, 100, 100)
    
    @property
    def name(self) -> str:
        return "flat"
    
    @property
    def description(self) -> str:
        return "Flat terrain at elevation 0 (useful for regression testing)"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {}
    
    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Flat",
            description="Perfectly flat terrain",
            extent=self._extent,
            source="procedural"
        )
    
    def evaluate(self, x: float, y: float) -> float:
        """Always returns 0."""
        return 0.0
    
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return a flat field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        z = np.zeros((resolution, resolution))
        return {
            "elevations": z,
            "x": x,
            "y": y,
        }
    
    def get_config(self) -> Dict[str, Any]:
        return {"type": "flat"}


class SingleSlopeTerrainProvider(TerrainProvider):
    """Planar terrain rising consistently in one selected direction."""

    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        slope: float = 1.0,
        direction: str = "x",
    ):
        self._extent = extent
        self._slope = slope
        self._direction = direction

    @property
    def name(self) -> str:
        return "single_slope"

    @property
    def description(self) -> str:
        return "Planar terrain with a single continuous slope"

    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "slope": ParameterSchema(
                name="slope", type="float", description="Slope height across the extent",
                default=1.0, min_value=0.0,
            ),
            "direction": ParameterSchema(
                name="direction", type="choice", description="Direction of ascent",
                default="x", choices=["x", "y"],
            ),
        }

    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Single Slope", description="Planar single-slope terrain",
            extent=self._extent, source="procedural",
        )

    def evaluate(self, x: float, y: float) -> float:
        """Evaluate the normalized planar slope for scalar or array coordinates."""
        min_x, min_y, max_x, max_y = self._extent
        if self._direction == "y":
            normalized = (np.asarray(y) - min_y) / (max_y - min_y)
        else:
            normalized = (np.asarray(x) - min_x) / (max_x - min_x)
        return self._slope * np.clip(normalized, 0.0, 1.0)

    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        return {"elevations": self.evaluate(X, Y), "x": x, "y": y}

    def get_config(self) -> Dict[str, Any]:
        return {"type": "single_slope", "slope": self._slope, "direction": self._direction}


class HillTerrainProvider(TerrainProvider):
    """Hill terrain: Gaussian bump centered in the middle."""
    
    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        peak_height: float = 1.0,
        sigma: Optional[float] = None,
    ):
        self._extent = extent
        self._peak_height = peak_height
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        # Default sigma is 1/6 of the smaller dimension
        self._sigma = sigma if sigma is not None else min(width, height) / 6
    
    @property
    def name(self) -> str:
        return "hill"
    
    @property
    def description(self) -> str:
        return "Hill: Gaussian bump centered on terrain"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "peak_height": ParameterSchema(
                name="peak_height",
                type="float",
                description="Height of the hill peak",
                default=1.0,
                min_value=0.0,
            ),
            "sigma": ParameterSchema(
                name="sigma",
                type="float",
                description="Width of the hill (standard deviation)",
                default=None,
            ),
        }
    
    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Hill",
            description="Gaussian hill centered on terrain",
            extent=self._extent,
            source="procedural"
        )
    
    def evaluate(self, x: float, y: float) -> float:
        """Evaluate elevation using 2D Gaussian."""
        min_x, min_y, max_x, max_y = self._extent
        cx = (max_x + min_x) / 2  # Center X
        cy = (max_y + min_y) / 2  # Center Y
        distance_squared = (x - cx) ** 2 + (y - cy) ** 2
        return self._peak_height * np.exp(-distance_squared / (2 * self._sigma ** 2))
    
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return sampled hill field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        Z = self.evaluate(X, Y)
        return {
            "elevations": Z,
            "x": x,
            "y": y,
        }
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "hill",
            "peak_height": self._peak_height,
            "sigma": self._sigma,
        }


class RidgeTerrainProvider(TerrainProvider):
    """Ridge terrain: elongated hill along one axis."""
    
    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        peak_height: float = 1.0,
        orientation: str = "y",  # "x" or "y"
        width: Optional[float] = None,
    ):
        self._extent = extent
        self._peak_height = peak_height
        self._orientation = orientation
        min_x, min_y, max_x, max_y = extent
        dim_x = max_x - min_x
        dim_y = max_y - min_y
        self._width = width if width is not None else min(dim_x, dim_y) / 8
    
    @property
    def name(self) -> str:
        return "ridge"
    
    @property
    def description(self) -> str:
        return "Ridge: elongated hill (orientation selectable)"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "peak_height": ParameterSchema(
                name="peak_height",
                type="float",
                description="Ridge peak height",
                default=1.0,
                min_value=0.0,
            ),
            "orientation": ParameterSchema(
                name="orientation",
                type="choice",
                description="Ridge direction",
                default="y",
                choices=["x", "y"],
            ),
            "width": ParameterSchema(
                name="width",
                type="float",
                description="Ridge width",
                default=None,
            ),
        }
    
    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Ridge",
            description="Elongated ridge",
            extent=self._extent,
            source="procedural"
        )
    
    def evaluate(self, x: float, y: float) -> float:
        """Evaluate ridge elevation."""
        min_x, min_y, max_x, max_y = self._extent
        if self._orientation == "y":
            center = (max_x + min_x) / 2
            return self._peak_height * np.exp(-((x - center) ** 2) / (2 * self._width ** 2))
        else:  # "x"
            center = (max_y + min_y) / 2
            return self._peak_height * np.exp(-((y - center) ** 2) / (2 * self._width ** 2))
    
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return sampled ridge field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        Z = self.evaluate(X, Y)
        return {
            "elevations": Z,
            "x": x,
            "y": y,
        }
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "ridge",
            "peak_height": self._peak_height,
            "orientation": self._orientation,
            "width": self._width,
        }


class ShoulderTerrainProvider(TerrainProvider):
    """Broad shoulder between two converging valley channels."""
    
    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        peak_height: float = 1.0,
        asymmetry: float = 0.7,  # How asymmetric the slopes are
    ):
        self._extent = extent
        self._peak_height = peak_height
        self._asymmetry = asymmetry
        min_x, min_y, max_x, max_y = extent
        self._width = min(max_x - min_x, max_y - min_y) / 12
    
    @property
    def name(self) -> str:
        return "shoulder"
    
    @property
    def description(self) -> str:
        return "Shoulder: broad landform between converging valleys"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "peak_height": ParameterSchema(
                name="peak_height",
                type="float",
                description="Shoulder height",
                default=1.0,
                min_value=0.0,
            ),
            "asymmetry": ParameterSchema(
                name="asymmetry",
                type="float",
                description="Asymmetry factor (0-1)",
                default=0.7,
                min_value=0.0,
                max_value=1.0,
            ),
        }
    
    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Shoulder",
            description="Broad elevated shoulder between two converging valleys",
            extent=self._extent,
            source="procedural"
        )
    
    def evaluate(self, x: float, y: float) -> float:
        """Evaluate a broad shoulder between two converging channels."""
        min_x, min_y, max_x, max_y = self._extent
        width = max_x - min_x
        height = max_y - min_y
        junction_x = min_x + width * 0.5
        junction_y = min_y + height * 0.35
        branch_y = min_y + height * 0.9
        left_x = min_x + width * 0.12
        right_x = min_x + width * 0.88

        # The two low channels converge toward the lower centre, leaving a
        # broad raised shoulder between them.
        branch_fraction = np.clip((y - junction_y) / (branch_y - junction_y), 0.0, 1.0)
        left_channel_x = junction_x + (left_x - junction_x) * branch_fraction
        right_channel_x = junction_x + (right_x - junction_x) * branch_fraction
        left_distance = np.abs(x - left_channel_x)
        right_distance = np.abs(x - right_channel_x)
        left_sigma = self._width * (0.7 - 0.4 * self._asymmetry)
        right_sigma = self._width * (0.7 + 0.4 * self._asymmetry)

        left_cut = np.exp(-(left_distance ** 2) / (2 * left_sigma ** 2))
        right_cut = np.exp(-(right_distance ** 2) / (2 * right_sigma ** 2))
        channel_cuts = np.maximum(left_cut, right_cut)
        shoulder_base = self._peak_height * (0.8 + 0.2 * np.asarray(branch_fraction))
        return shoulder_base * (1.0 - 0.9 * channel_cuts)
    
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return sampled shoulder field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        Z = self.evaluate(X, Y)
        return {
            "elevations": Z,
            "x": x,
            "y": y,
        }
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "shoulder",
            "peak_height": self._peak_height,
            "asymmetry": self._asymmetry,
        }


class TwinPeaksTerrainProvider(TerrainProvider):
    """Twin peaks joined by a saddle."""
    
    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        peak_height: float = 1.0,
        saddle_height: float = 0.5,
        peak_separation: float = 40.0,
    ):
        self._extent = extent
        self._peak_height = peak_height
        self._saddle_height = saddle_height
        self._peak_separation = peak_separation
        min_x, min_y, max_x, max_y = extent
        self._sigma = min(max_x - min_x, max_y - min_y) / 12
    
    @property
    def name(self) -> str:
        return "twin_peaks"
    
    @property
    def description(self) -> str:
        return "Twin peaks joined by a saddle"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "peak_height": ParameterSchema(
                name="peak_height",
                type="float",
                description="Height of each peak",
                default=1.0,
                min_value=0.0,
            ),
            "saddle_height": ParameterSchema(
                name="saddle_height",
                type="float",
                description="Height of saddle between peaks",
                default=0.5,
                min_value=0.0,
            ),
            "peak_separation": ParameterSchema(
                name="peak_separation",
                type="float",
                description="Distance between peaks",
                default=40.0,
                min_value=10.0,
            ),
        }
    
    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Twin Peaks",
            description="Two peaks separated by a saddle",
            extent=self._extent,
            source="procedural"
        )
    
    def evaluate(self, x: float, y: float) -> float:
        """Evaluate twin peaks elevation."""
        min_x, min_y, max_x, max_y = self._extent
        cx = (max_x + min_x) / 2
        cy = (max_y + min_y) / 2
        # Two radial Gaussian peaks separated along X.
        peak1_x = cx - self._peak_separation / 2
        peak2_x = cx + self._peak_separation / 2
        
        dist1_squared = (x - peak1_x) ** 2 + (y - cy) ** 2
        dist2_squared = (x - peak2_x) ** 2 + (y - cy) ** 2
        
        h1 = self._peak_height * np.exp(-dist1_squared / (2 * self._sigma ** 2))
        h2 = self._peak_height * np.exp(-dist2_squared / (2 * self._sigma ** 2))
        
        # Keep a lower central saddle between the two localized peaks.
        saddle_distance_squared = (x - cx) ** 2 + (y - cy) ** 2
        saddle_contribution = self._saddle_height * np.exp(
            -saddle_distance_squared / (self._peak_separation ** 2)
        )
        
        return np.maximum(np.maximum(h1, h2), saddle_contribution)
    
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return sampled twin peaks field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        Z = self.evaluate(X, Y)
        return {
            "elevations": Z,
            "x": x,
            "y": y,
        }
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "twin_peaks",
            "peak_height": self._peak_height,
            "saddle_height": self._saddle_height,
            "peak_separation": self._peak_separation,
        }


class ValleyTerrainProvider(TerrainProvider):
    """Valley terrain: inverted hill."""
    
    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        depth: float = 1.0,
        sigma: Optional[float] = None,
    ):
        self._extent = extent
        self._depth = depth
        min_x, min_y, max_x, max_y = extent
        width = max_x - min_x
        height = max_y - min_y
        self._sigma = sigma if sigma is not None else min(width, height) / 6
    
    @property
    def name(self) -> str:
        return "valley"
    
    @property
    def description(self) -> str:
        return "Valley: inverted Gaussian bump"
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "depth": ParameterSchema(
                name="depth",
                type="float",
                description="Valley depth",
                default=1.0,
                min_value=0.0,
            ),
        }
    
    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Valley",
            description="Valley depression",
            extent=self._extent,
            source="procedural"
        )
    
    def evaluate(self, x: float, y: float) -> float:
        """Evaluate valley elevation."""
        min_x, min_y, max_x, max_y = self._extent
        cy = (max_y + min_y) / 2
        # Valley: inverted Gaussian (low at center, high at edges)
        return self._depth * (1 - np.exp(-((y - cy) ** 2) / (2 * self._sigma ** 2)))
    
    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return sampled valley field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        Z = self.evaluate(X, Y)
        return {
            "elevations": Z,
            "x": x,
            "y": y,
        }
    
    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "valley",
            "depth": self._depth,
            "sigma": self._sigma,
        }


class ConvergingValleysTerrainProvider(TerrainProvider):
    """Y-shaped valley network with two branches joining a main valley."""

    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        depth: float = 1.0,
        valley_width: float = 0.1,
    ):
        self._extent = extent
        self._depth = depth
        self._valley_width = valley_width

    @property
    def name(self) -> str:
        return "converging_valleys"

    @property
    def description(self) -> str:
        return "Two valley branches joining into one, separated by a shoulder"

    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "depth": ParameterSchema(
                name="depth",
                type="float",
                description="Valley depth",
                default=1.0,
                min_value=0.0,
            ),
            "valley_width": ParameterSchema(
                name="valley_width",
                type="float",
                description="Valley channel width as a fraction of canvas size",
                default=0.1,
                min_value=0.01,
                max_value=0.5,
            ),
        }

    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Converging Valleys",
            description="Y-shaped valley network with a raised central shoulder",
            extent=self._extent,
            source="procedural",
        )

    @staticmethod
    def _segment_distance_squared(x, y, start, end):
        """Return squared distance from each coordinate to a line segment."""
        start = np.asarray(start, dtype=float)
        end = np.asarray(end, dtype=float)
        dx = end - start
        length_squared = np.dot(dx, dx)
        projection = ((x - start[0]) * dx[0] + (y - start[1]) * dx[1]) / length_squared
        projection = np.clip(projection, 0.0, 1.0)
        closest_x = start[0] + projection * dx[0]
        closest_y = start[1] + projection * dx[1]
        return (x - closest_x) ** 2 + (y - closest_y) ** 2

    def evaluate(self, x: float, y: float) -> float:
        """Evaluate the Y-shaped valley for scalar or array coordinates."""
        min_x, min_y, max_x, max_y = self._extent
        width = max_x - min_x
        height = max_y - min_y
        junction = (min_x + width * 0.5, min_y + height * 0.5)
        left_branch = (min_x + width * 0.12, min_y + height * 0.9)
        right_branch = (min_x + width * 0.88, min_y + height * 0.9)
        trunk_end = (min_x + width * 0.5, min_y + height * 0.05)
        
        distance_squared = np.minimum.reduce([
            self._segment_distance_squared(x, y, left_branch, junction),
            self._segment_distance_squared(x, y, right_branch, junction),
            self._segment_distance_squared(x, y, junction, trunk_end),
        ])
        sigma = min(width, height) * self._valley_width
        return self._depth * (1 - np.exp(-distance_squared / (2 * sigma ** 2)))

    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        """Return a sampled Y-shaped valley field."""
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        return {"elevations": self.evaluate(X, Y), "x": x, "y": y}

    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "converging_valleys",
            "depth": self._depth,
            "valley_width": self._valley_width,
        }


class ThreeConvergingRidgesTerrainProvider(TerrainProvider):
    """Three elevated Gaussian ridges converging at a central junction."""

    def __init__(
        self,
        extent: Tuple[float, float, float, float] = (0, 0, 100, 100),
        peak_height: float = 1.0,
        ridge_width: float = 0.1,
    ):
        self._extent = extent
        self._peak_height = peak_height
        self._ridge_width = ridge_width

    @property
    def name(self) -> str:
        return "three_converging_ridges"

    @property
    def description(self) -> str:
        return "Three elevated ridges converging at one central junction"

    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "peak_height": ParameterSchema(
                name="peak_height", type="float", description="Ridge height",
                default=1.0, min_value=0.0,
            ),
            "ridge_width": ParameterSchema(
                name="ridge_width", type="float", description="Ridge width as a fraction of canvas size",
                default=0.1, min_value=0.01, max_value=0.5,
            ),
        }

    @property
    def metadata(self) -> TerrainMetadata:
        return TerrainMetadata(
            name="Three Converging Ridges",
            description="Three raised ridge branches meeting at a central junction",
            extent=self._extent, source="procedural",
        )

    @staticmethod
    def _segment_distance_squared(x, y, start, end):
        start = np.asarray(start, dtype=float)
        end = np.asarray(end, dtype=float)
        delta = end - start
        fraction = ((x - start[0]) * delta[0] + (y - start[1]) * delta[1]) / np.dot(delta, delta)
        fraction = np.clip(fraction, 0.0, 1.0)
        closest_x = start[0] + fraction * delta[0]
        closest_y = start[1] + fraction * delta[1]
        return (x - closest_x) ** 2 + (y - closest_y) ** 2

    def evaluate(self, x: float, y: float) -> float:
        """Evaluate three converging ridge branches for scalar or array coordinates."""
        min_x, min_y, max_x, max_y = self._extent
        width = max_x - min_x
        height = max_y - min_y
        junction = (min_x + width * 0.5, min_y + height * 0.5)
        endpoints = [
            (min_x + width * 0.12, min_y + height * 0.88),
            (min_x + width * 0.88, min_y + height * 0.88),
            (min_x + width * 0.5, min_y + height * 0.08),
        ]
        distance_squared = np.minimum.reduce([
            self._segment_distance_squared(x, y, endpoint, junction)
            for endpoint in endpoints
        ])
        sigma = min(width, height) * self._ridge_width
        return self._peak_height * np.exp(-distance_squared / (2 * sigma ** 2))

    def sample_field(self, resolution: int = 256) -> Dict[str, Any]:
        min_x, min_y, max_x, max_y = self._extent
        x = np.linspace(min_x, max_x, resolution)
        y = np.linspace(min_y, max_y, resolution)
        X, Y = np.meshgrid(x, y)
        return {"elevations": self.evaluate(X, Y), "x": x, "y": y}

    def get_config(self) -> Dict[str, Any]:
        return {
            "type": "three_converging_ridges",
            "peak_height": self._peak_height,
            "ridge_width": self._ridge_width,
        }
