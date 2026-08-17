"""
Space-syntax analysis measures.
"""

import networkx as nx
from typing import Dict, Any, List, Optional
from shapely.geometry import Polygon, LineString

from .core import SpaceSyntaxMeasure, Representation, ParameterSchema


class MeanDepthMeasure(SpaceSyntaxMeasure):
    """
    Mean Depth: average topological distance from a node to all others.
    
    Lower values indicate more central nodes.
    Normalized by graph size: mean_depth = sum_distances / (num_nodes - 1)
    """
    
    @property
    def name(self) -> str:
        return "mean_depth"
    
    @property
    def description(self) -> str:
        return (
            "Mean Depth: average topological distance from each node to all others. "
            "Lower values = more central. Normalized by (graph_size - 1)."
        )
    
    @property
    def supported_representations(self) -> List[str]:
        return ["cell_graph", "dual_graph"]
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {}
    
    def compute(
        self,
        representation: Representation,
        **kwargs
    ) -> Dict[int, float]:
        """Compute mean depth for each node."""
        # Build networkx graph
        graph = nx.Graph()
        graph.add_nodes_from(representation.nodes)
        graph.add_edges_from(representation.edges)
        
        result = {}
        
        if graph.number_of_nodes() == 0:
            return result
        
        for node in representation.nodes:
            if not nx.has_path(graph, node, list(representation.nodes)[0]):
                # Node is disconnected
                result[node] = float('inf')
                continue
            
            lengths = nx.single_source_shortest_path_length(graph, node)
            # Normalize by (graph_size - 1)
            if len(representation.nodes) > 1:
                mean_depth = sum(lengths.values()) / (len(representation.nodes) - 1)
            else:
                mean_depth = 0.0
            result[node] = mean_depth
        
        return result


class ConnectivityMeasure(SpaceSyntaxMeasure):
    """
    Connectivity: number of directly adjacent nodes (degree).
    
    Higher values indicate more connected nodes.
    """
    
    @property
    def name(self) -> str:
        return "connectivity"
    
    @property
    def description(self) -> str:
        return (
            "Connectivity: number of directly adjacent nodes (graph degree). "
            "Higher values indicate local hub nodes."
        )
    
    @property
    def supported_representations(self) -> List[str]:
        return ["cell_graph", "dual_graph"]
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {}
    
    def compute(
        self,
        representation: Representation,
        **kwargs
    ) -> Dict[int, float]:
        """Compute connectivity (degree) for each node."""
        # Build networkx graph
        graph = nx.Graph()
        graph.add_nodes_from(representation.nodes)
        graph.add_edges_from(representation.edges)
        
        result = {}
        for node in representation.nodes:
            result[node] = float(graph.degree(node))
        
        return result


class IntegrationMeasure(SpaceSyntaxMeasure):
    """
    Integration: normalized mean depth (relative to graph).
    
    RA (Relative Asymmetry) normalized measure.
    Higher values indicate more integrated (central) spaces.
    """
    
    @property
    def name(self) -> str:
        return "integration"
    
    @property
    def description(self) -> str:
        return (
            "Integration: normalized mean depth (RA measure). "
            "Higher values = more integrated. Accounts for graph structure."
        )
    
    @property
    def supported_representations(self) -> List[str]:
        return ["cell_graph", "dual_graph"]
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {}
    
    def compute(
        self,
        representation: Representation,
        **kwargs
    ) -> Dict[int, float]:
        """Compute integration (RA-normalized)."""
        # Build networkx graph
        graph = nx.Graph()
        graph.add_nodes_from(representation.nodes)
        graph.add_edges_from(representation.edges)
        
        n = len(representation.nodes)
        if n <= 1:
            return {node: 0.0 for node in representation.nodes}
        
        # Expected mean depth for random graph
        # RA = (MD - E[MD]) / (E[MD])  where E[MD] ≈ (2(n-1)/3) for planar graphs
        # Simpler normalized: integration = 1 / (mean_depth + 1)
        result = {}
        
        for node in representation.nodes:
            lengths = nx.single_source_shortest_path_length(graph, node)
            mean_depth = sum(lengths.values()) / (n - 1)
            # Integration: higher = more central
            integration = 1.0 / (mean_depth + 1.0)
            result[node] = integration
        
        return result


class ChoiceMeasure(SpaceSyntaxMeasure):
    """
    Choice: betweenness centrality normalized.
    
    Measures how often a node lies on shortest paths between other nodes.
    Higher values indicate nodes that are important for movement/navigation.
    """
    
    @property
    def name(self) -> str:
        return "choice"
    
    @property
    def description(self) -> str:
        return (
            "Choice: betweenness centrality. "
            "Measures frequency on shortest paths between all pairs. "
            "Higher = more important for movement."
        )
    
    @property
    def supported_representations(self) -> List[str]:
        return ["cell_graph", "dual_graph"]
    
    @property
    def parameters(self) -> Dict[str, ParameterSchema]:
        return {
            "normalized": ParameterSchema(
                name="normalized",
                type="bool",
                description="Normalize by (n-1)(n-2)/2",
                default=True,
            ),
        }
    
    def compute(
        self,
        representation: Representation,
        **kwargs
    ) -> Dict[int, float]:
        """Compute betweenness centrality (choice)."""
        # Build networkx graph
        graph = nx.Graph()
        graph.add_nodes_from(representation.nodes)
        graph.add_edges_from(representation.edges)
        
        normalized = kwargs.get("normalized", True)
        
        # NetworkX betweenness centrality already returns normalized by default
        result = nx.betweenness_centrality(graph, normalized=normalized)
        
        # Ensure all nodes are present
        for node in representation.nodes:
            if node not in result:
                result[node] = 0.0
        
        return result
