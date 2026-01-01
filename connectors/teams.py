import yaml
from .base import BaseConnector, Node, Edge


class TeamsConnector(BaseConnector):
    def parse(self) -> tuple[list[Node], list[Edge]]:
        try:
            with open(self.file_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error parsing {self.file_path}: {e}")
            return [], []

        teams = data.get("teams", [])

        for team in teams:
            name = team.get("name")
            if not name:
                continue

            node = Node(
                id=f"team:{name}",
                type="team",
                name=name,
                properties={
                    "lead": team.get("lead"),
                    "slack_channel": team.get("slack_channel"),
                    "pagerduty_schedule": team.get("pagerduty_schedule"),
                },
            )
            self._add_node(node)

            owns = team.get("owns", [])
            for owned_item in owns:
                edge = Edge(
                    id=f"edge:{name}-owns-{owned_item}",
                    type="owns",
                    source=f"team:{name}",
                    target=owned_item,
                    properties={},
                )
                self._add_edge(edge)

        return self.nodes, self.edges

    def resolve_ownership_targets(self, all_nodes: list[Node]) -> list[Edge]:
        resolved_edges = []
        node_map = {}
        
        for node in all_nodes:
            node_map[node.name] = node.id
            node_map[node.id] = node.id

        for edge in self.edges:
            if edge.type == "owns":
                target = edge.target
                if target in node_map:
                    resolved_edge = Edge(
                        id=edge.id,
                        type=edge.type,
                        source=edge.source,
                        target=node_map[target],
                        properties=edge.properties,
                    )
                    resolved_edges.append(resolved_edge)
                else:
                    for node_name, node_id in node_map.items():
                        if target in node_name or node_name.endswith(target):
                            resolved_edge = Edge(
                                id=f"edge:{edge.source.split(':')[1]}-owns-{node_id.split(':')[1]}",
                                type=edge.type,
                                source=edge.source,
                                target=node_id,
                                properties=edge.properties,
                            )
                            resolved_edges.append(resolved_edge)
                            break

        return resolved_edges
