import re
import yaml
from .base import BaseConnector, Node, Edge


class DockerComposeConnector(BaseConnector):
    DATABASE_IMAGES = ["postgres", "mysql", "mariadb", "mongodb", "cassandra"]
    CACHE_IMAGES = ["redis", "memcached"]

    def parse(self) -> tuple[list[Node], list[Edge]]:
        try:
            with open(self.file_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error parsing {self.file_path}: {e}")
            return [], []

        services = data.get("services", {})

        for name, config in services.items():
            node_type = self._infer_node_type(name, config)
            labels = config.get("labels", {})
            
            properties = {
                "team": labels.get("team"),
                "oncall": labels.get("oncall"),
            }

            ports = config.get("ports", [])
            if ports:
                first_port = ports[0]
                if isinstance(first_port, str) and ":" in first_port:
                    properties["port"] = int(first_port.split(":")[1])
                elif isinstance(first_port, int):
                    properties["port"] = first_port

            for key, value in labels.items():
                if key not in ["team", "oncall"]:
                    properties[key] = value

            properties = {k: v for k, v in properties.items() if v is not None}

            node = Node(
                id=f"{node_type}:{name}",
                type=node_type,
                name=name,
                properties=properties,
            )
            self._add_node(node)

        for name, config in services.items():
            source_type = self._infer_node_type(name, config)
            source_id = f"{source_type}:{name}"

            depends_on = config.get("depends_on", [])
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())
            
            for dep in depends_on:
                dep_config = services.get(dep, {})
                dep_type = self._infer_node_type(dep, dep_config)
                target_id = f"{dep_type}:{dep}"
                
                edge_type = self._infer_edge_type(dep_type)
                edge = Edge(
                    id=f"edge:{name}-{edge_type}-{dep}",
                    type=edge_type,
                    source=source_id,
                    target=target_id,
                )
                self._add_edge(edge)

            environment = config.get("environment", [])
            env_dict = self._parse_environment(environment)
            
            for key, value in env_dict.items():
                if "_URL" in key and value:
                    target_name = self._extract_service_from_url(value)
                    if target_name and target_name in services:
                        target_config = services.get(target_name, {})
                        target_type = self._infer_node_type(target_name, target_config)
                        target_id = f"{target_type}:{target_name}"
                        
                        if target_id != source_id:
                            edge_type = self._infer_edge_type(target_type)
                            edge = Edge(
                                id=f"edge:{name}-{edge_type}-{target_name}",
                                type=edge_type,
                                source=source_id,
                                target=target_id,
                            )
                            self._add_edge(edge)

        return self.nodes, self.edges

    def _infer_node_type(self, name: str, config: dict) -> str:
        labels = config.get("labels", {})
        if labels.get("type") == "database":
            return "database"
        if labels.get("type") == "cache":
            return "cache"

        image = config.get("image", "")
        for db_image in self.DATABASE_IMAGES:
            if db_image in image.lower():
                return "database"
        for cache_image in self.CACHE_IMAGES:
            if cache_image in image.lower():
                return "cache"

        if any(x in name.lower() for x in ["db", "database", "postgres", "mysql"]):
            return "database"
        if any(x in name.lower() for x in ["redis", "cache", "memcached"]):
            return "cache"

        return "service"

    def _infer_edge_type(self, target_type: str) -> str:
        if target_type == "database":
            return "reads_from"
        if target_type == "cache":
            return "uses"
        return "calls"

    def _parse_environment(self, environment) -> dict:
        if isinstance(environment, dict):
            return environment
        if isinstance(environment, list):
            result = {}
            for item in environment:
                if isinstance(item, str) and "=" in item:
                    key, value = item.split("=", 1)
                    result[key] = value
            return result
        return {}

    def _extract_service_from_url(self, url: str) -> str | None:
        patterns = [
            r"://([^:/@]+):",
            r"://([^:/@]+)/",
            r"@([^:/@]+):",
            r"http://([^:/@]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
