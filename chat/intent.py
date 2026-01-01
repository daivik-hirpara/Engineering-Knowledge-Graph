from graph.query import QueryEngine


class IntentParser:
    def __init__(self, query_engine: QueryEngine):
        self.query_engine = query_engine
        self.last_result = None
        self.last_entity = None

    def execute_intent(self, intent_data: dict) -> dict:
        intent = intent_data.get("intent", "UNKNOWN")
        params = intent_data.get("params", {})
        clarification = intent_data.get("clarification")

        if clarification:
            return {"type": "clarification", "message": clarification}

        handlers = {
            "OWNERSHIP": self._handle_ownership,
            "DEPENDENCY_DOWNSTREAM": self._handle_downstream,
            "DEPENDENCY_UPSTREAM": self._handle_upstream,
            "BLAST_RADIUS": self._handle_blast_radius,
            "PATH": self._handle_path,
            "LIST_NODES": self._handle_list_nodes,
            "NODE_INFO": self._handle_node_info,
            "SEARCH": self._handle_search,
            "TEAM_OWNS": self._handle_team_owns,
        }

        handler = handlers.get(intent, self._handle_unknown)
        result = handler(params)
        
        if result.get("type") != "error":
            self.last_result = result
            if "node" in result:
                self.last_entity = result.get("node", {}).get("id")

        return result

    def _resolve_node_id(self, identifier: str) -> str | None:
        if ":" in identifier:
            node = self.query_engine.get_node(identifier)
            if node:
                return identifier

        for prefix in ["service:", "database:", "cache:", "team:"]:
            node_id = f"{prefix}{identifier}"
            node = self.query_engine.get_node(node_id)
            if node:
                return node_id

        results = self.query_engine.search_nodes(identifier)
        if results:
            return results[0].get("id")

        return None

    def _handle_ownership(self, params: dict) -> dict:
        node_id = params.get("node_id")
        if not node_id:
            return {"type": "error", "message": "Please specify which service or resource you're asking about."}

        resolved_id = self._resolve_node_id(node_id)
        if not resolved_id:
            return {"type": "error", "message": f"Could not find '{node_id}' in the graph."}

        owner = self.query_engine.get_owner(resolved_id)
        node = self.query_engine.get_node(resolved_id)

        return {
            "type": "ownership",
            "node": node,
            "owner": owner,
        }

    def _handle_downstream(self, params: dict) -> dict:
        node_id = params.get("node_id")
        if not node_id:
            return {"type": "error", "message": "Please specify which service you're asking about."}

        resolved_id = self._resolve_node_id(node_id)
        if not resolved_id:
            return {"type": "error", "message": f"Could not find '{node_id}' in the graph."}

        dependencies = self.query_engine.downstream(resolved_id)
        node = self.query_engine.get_node(resolved_id)

        return {
            "type": "dependencies",
            "direction": "downstream",
            "node": node,
            "dependencies": dependencies,
        }

    def _handle_upstream(self, params: dict) -> dict:
        node_id = params.get("node_id")
        if not node_id:
            return {"type": "error", "message": "Please specify which resource you're asking about."}

        resolved_id = self._resolve_node_id(node_id)
        if not resolved_id:
            return {"type": "error", "message": f"Could not find '{node_id}' in the graph."}

        dependents = self.query_engine.upstream(resolved_id)
        node = self.query_engine.get_node(resolved_id)

        return {
            "type": "dependents",
            "direction": "upstream",
            "node": node,
            "dependents": dependents,
        }

    def _handle_blast_radius(self, params: dict) -> dict:
        node_id = params.get("node_id")
        if not node_id:
            return {"type": "error", "message": "Please specify which resource you're asking about."}

        resolved_id = self._resolve_node_id(node_id)
        if not resolved_id:
            return {"type": "error", "message": f"Could not find '{node_id}' in the graph."}

        result = self.query_engine.blast_radius(resolved_id)
        if not result:
            return {"type": "error", "message": f"Could not analyze blast radius for '{node_id}'."}

        return {
            "type": "blast_radius",
            "node": result.node,
            "upstream": result.upstream,
            "downstream": result.downstream,
            "affected_teams": result.affected_teams,
            "total_affected": result.total_affected,
        }

    def _handle_path(self, params: dict) -> dict:
        from_id = params.get("from_id")
        to_id = params.get("to_id")

        if not from_id or not to_id:
            return {"type": "error", "message": "Please specify both the start and end points."}

        resolved_from = self._resolve_node_id(from_id)
        resolved_to = self._resolve_node_id(to_id)

        if not resolved_from:
            return {"type": "error", "message": f"Could not find '{from_id}' in the graph."}
        if not resolved_to:
            return {"type": "error", "message": f"Could not find '{to_id}' in the graph."}

        path = self.query_engine.path(resolved_from, resolved_to)

        return {
            "type": "path",
            "from": self.query_engine.get_node(resolved_from),
            "to": self.query_engine.get_node(resolved_to),
            "path": path,
        }

    def _handle_list_nodes(self, params: dict) -> dict:
        node_type = params.get("node_type")
        nodes = self.query_engine.get_nodes(node_type)

        return {
            "type": "list",
            "node_type": node_type,
            "nodes": nodes,
            "count": len(nodes),
        }

    def _handle_node_info(self, params: dict) -> dict:
        node_id = params.get("node_id")
        if not node_id:
            return {"type": "error", "message": "Please specify which node you're asking about."}

        resolved_id = self._resolve_node_id(node_id)
        if not resolved_id:
            return {"type": "error", "message": f"Could not find '{node_id}' in the graph."}

        node = self.query_engine.get_node(resolved_id)
        owner = self.query_engine.get_owner(resolved_id)
        downstream = self.query_engine.downstream(resolved_id)
        upstream = self.query_engine.upstream(resolved_id)

        return {
            "type": "node_info",
            "node": node,
            "owner": owner,
            "downstream": downstream,
            "upstream": upstream,
        }

    def _handle_search(self, params: dict) -> dict:
        query_text = params.get("query_text", "")
        if not query_text:
            return {"type": "error", "message": "Please specify what to search for."}

        results = self.query_engine.search_nodes(query_text)

        return {
            "type": "search",
            "query": query_text,
            "results": results,
            "count": len(results),
        }

    def _handle_team_owns(self, params: dict) -> dict:
        team_name = params.get("team_name")
        if not team_name:
            return {"type": "error", "message": "Please specify which team you're asking about."}

        if not team_name.startswith("team:"):
            team_name_clean = team_name.replace("@", "")
            if not "-team" in team_name_clean:
                team_name_clean = f"{team_name_clean}-team" if team_name_clean else team_name_clean
        else:
            team_name_clean = team_name.replace("team:", "")

        owned = self.query_engine.get_nodes_owned_by_team(team_name_clean)
        team = self.query_engine.get_node(f"team:{team_name_clean}")

        return {
            "type": "team_ownership",
            "team": team,
            "owned_resources": owned,
        }

    def _handle_unknown(self, params: dict) -> dict:
        return {
            "type": "error",
            "message": "I couldn't understand that query. Try asking about ownership, dependencies, blast radius, or connections between services."
        }

    def get_graph_schema(self) -> dict:
        stats = self.query_engine.get_graph_stats()
        
        services = self.query_engine.get_nodes("service")
        databases = self.query_engine.get_nodes("database")
        caches = self.query_engine.get_nodes("cache")
        teams = self.query_engine.get_nodes("team")

        return {
            "statistics": stats,
            "services": [s.get("name") for s in services],
            "databases": [d.get("name") for d in databases],
            "caches": [c.get("name") for c in caches],
            "teams": [t.get("name") for t in teams],
        }
