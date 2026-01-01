from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    id: str
    type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "properties": self.properties,
        }


@dataclass
class Edge:
    id: str
    type: str
    source: str
    target: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "properties": self.properties,
        }


class BaseConnector(ABC):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    @abstractmethod
    def parse(self) -> tuple[list[Node], list[Edge]]:
        pass

    def _add_node(self, node: Node) -> None:
        existing = next((n for n in self.nodes if n.id == node.id), None)
        if existing:
            existing.properties.update(node.properties)
        else:
            self.nodes.append(node)

    def _add_edge(self, edge: Edge) -> None:
        existing = next((e for e in self.edges if e.id == edge.id), None)
        if not existing:
            self.edges.append(edge)
