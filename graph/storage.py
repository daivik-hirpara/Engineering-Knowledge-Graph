import os
from neo4j import GraphDatabase
from connectors.base import Node, Edge


class GraphStorage:
    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
    ):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self._driver = None

    def connect(self) -> None:
        if not self._driver:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def clear_all(self) -> None:
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def upsert_node(self, node: Node) -> None:
        query = """
        MERGE (n {id: $id})
        SET n.type = $type,
            n.name = $name,
            n += $properties
        """
        with self._driver.session() as session:
            session.run(
                query,
                id=node.id,
                type=node.type,
                name=node.name,
                properties=node.properties,
            )

    def upsert_edge(self, edge: Edge) -> None:
        query = """
        MATCH (source {id: $source})
        MATCH (target {id: $target})
        MERGE (source)-[r:EDGE {id: $id}]->(target)
        SET r.type = $type,
            r += $properties
        """
        with self._driver.session() as session:
            session.run(
                query,
                id=edge.id,
                type=edge.type,
                source=edge.source,
                target=edge.target,
                properties=edge.properties,
            )

    def get_node(self, node_id: str) -> dict | None:
        query = """
        MATCH (n {id: $id})
        RETURN n
        """
        with self._driver.session() as session:
            result = session.run(query, id=node_id)
            record = result.single()
            if record:
                return dict(record["n"])
            return None

    def get_nodes(self, node_type: str = None, filters: dict = None) -> list[dict]:
        if node_type:
            query = "MATCH (n {type: $type})"
            params = {"type": node_type}
        else:
            query = "MATCH (n)"
            params = {}

        if filters:
            conditions = []
            for key, value in filters.items():
                param_name = f"filter_{key}"
                conditions.append(f"n.{key} = ${param_name}")
                params[param_name] = value
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += " RETURN n"

        with self._driver.session() as session:
            result = session.run(query, **params)
            return [dict(record["n"]) for record in result]

    def delete_node(self, node_id: str) -> bool:
        query = """
        MATCH (n {id: $id})
        DETACH DELETE n
        RETURN count(n) as deleted
        """
        with self._driver.session() as session:
            result = session.run(query, id=node_id)
            record = result.single()
            return record["deleted"] > 0 if record else False

    def get_all_edges(self) -> list[dict]:
        query = """
        MATCH (source)-[r:EDGE]->(target)
        RETURN r.id as id, r.type as type, source.id as source, target.id as target, r as properties
        """
        with self._driver.session() as session:
            result = session.run(query)
            edges = []
            for record in result:
                edge_dict = {
                    "id": record["id"],
                    "type": record["type"],
                    "source": record["source"],
                    "target": record["target"],
                    "properties": {k: v for k, v in dict(record["properties"]).items() 
                                   if k not in ["id", "type"]},
                }
                edges.append(edge_dict)
            return edges

    def bulk_upsert_nodes(self, nodes: list[Node]) -> None:
        for node in nodes:
            self.upsert_node(node)

    def bulk_upsert_edges(self, edges: list[Edge]) -> None:
        for edge in edges:
            self.upsert_edge(edge)
