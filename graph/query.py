from dataclasses import dataclass
from .storage import GraphStorage


@dataclass
class BlastRadiusResult:
    node: dict
    upstream: list[dict]
    downstream: list[dict]
    affected_teams: list[dict]
    total_affected: int


class QueryEngine:
    def __init__(self, storage: GraphStorage):
        self.storage = storage

    def get_node(self, node_id: str) -> dict | None:
        return self.storage.get_node(node_id)

    def get_nodes(self, node_type: str = None, filters: dict = None) -> list[dict]:
        return self.storage.get_nodes(node_type, filters)

    def downstream(self, node_id: str, edge_types: list[str] = None) -> list[dict]:
        if edge_types:
            type_filter = " AND r.type IN $edge_types"
        else:
            type_filter = ""

        query = f"""
        MATCH (start {{id: $node_id}})
        MATCH path = (start)-[r:EDGE*1..10]->(downstream)
        WHERE ALL(rel IN relationships(path) WHERE true{type_filter})
        WITH DISTINCT downstream
        RETURN downstream
        """
        
        with self.storage._driver.session() as session:
            params = {"node_id": node_id}
            if edge_types:
                params["edge_types"] = edge_types
            result = session.run(query, **params)
            return [dict(record["downstream"]) for record in result]

    def upstream(self, node_id: str, edge_types: list[str] = None) -> list[dict]:
        if edge_types:
            type_filter = " AND r.type IN $edge_types"
        else:
            type_filter = ""

        query = f"""
        MATCH (target {{id: $node_id}})
        MATCH path = (upstream)-[r:EDGE*1..10]->(target)
        WHERE ALL(rel IN relationships(path) WHERE true{type_filter})
        WITH DISTINCT upstream
        RETURN upstream
        """
        
        with self.storage._driver.session() as session:
            params = {"node_id": node_id}
            if edge_types:
                params["edge_types"] = edge_types
            result = session.run(query, **params)
            return [dict(record["upstream"]) for record in result]

    def blast_radius(self, node_id: str) -> BlastRadiusResult:
        node = self.get_node(node_id)
        if not node:
            return None

        upstream = self.upstream(node_id)
        downstream = self.downstream(node_id)

        all_affected_ids = set()
        for n in upstream + downstream:
            all_affected_ids.add(n.get("id"))
        all_affected_ids.add(node_id)

        affected_teams = []
        for affected_id in all_affected_ids:
            team = self.get_owner(affected_id)
            if team and team not in affected_teams:
                affected_teams.append(team)

        return BlastRadiusResult(
            node=node,
            upstream=upstream,
            downstream=downstream,
            affected_teams=affected_teams,
            total_affected=len(all_affected_ids),
        )

    def path(self, from_id: str, to_id: str) -> list[dict]:
        query = """
        MATCH (start {id: $from_id}), (end {id: $to_id})
        MATCH path = shortestPath((start)-[*..15]-(end))
        UNWIND nodes(path) as node
        RETURN DISTINCT node
        """
        
        with self.storage._driver.session() as session:
            result = session.run(query, from_id=from_id, to_id=to_id)
            return [dict(record["node"]) for record in result]

    def get_owner(self, node_id: str) -> dict | None:
        query = """
        MATCH (team {type: 'team'})-[r:EDGE {type: 'owns'}]->(target {id: $node_id})
        RETURN team
        """
        
        with self.storage._driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            if record:
                return dict(record["team"])
            return None

    def get_nodes_owned_by_team(self, team_name: str) -> list[dict]:
        team_id = f"team:{team_name}"
        
        query = """
        MATCH (team {id: $team_id})-[r:EDGE {type: 'owns'}]->(owned)
        RETURN owned
        """
        
        with self.storage._driver.session() as session:
            result = session.run(query, team_id=team_id)
            return [dict(record["owned"]) for record in result]

    def get_services_using_node(self, node_id: str) -> list[dict]:
        return self.upstream(node_id)

    def search_nodes(self, query_text: str) -> list[dict]:
        query = """
        MATCH (n)
        WHERE toLower(n.name) CONTAINS toLower($query_text)
           OR toLower(n.id) CONTAINS toLower($query_text)
        RETURN n
        """
        
        with self.storage._driver.session() as session:
            result = session.run(query, query_text=query_text)
            return [dict(record["n"]) for record in result]

    def get_graph_stats(self) -> dict:
        query_nodes = "MATCH (n) RETURN count(n) as count"
        query_edges = "MATCH ()-[r]->() RETURN count(r) as count"
        query_types = "MATCH (n) RETURN DISTINCT n.type as type, count(n) as count"
        
        with self.storage._driver.session() as session:
            node_count = session.run(query_nodes).single()["count"]
            edge_count = session.run(query_edges).single()["count"]
            types = {r["type"]: r["count"] for r in session.run(query_types)}
            
            return {
                "total_nodes": node_count,
                "total_edges": edge_count,
                "nodes_by_type": types,
            }
