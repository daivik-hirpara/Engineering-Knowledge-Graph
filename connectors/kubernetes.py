import re
import yaml
from .base import BaseConnector, Node, Edge


class KubernetesConnector(BaseConnector):
    def parse(self) -> tuple[list[Node], list[Edge]]:
        try:
            with open(self.file_path, "r") as f:
                documents = list(yaml.safe_load_all(f))
        except Exception as e:
            print(f"Error parsing {self.file_path}: {e}")
            return [], []

        for doc in documents:
            if not doc:
                continue
            
            kind = doc.get("kind", "")
            if kind == "Deployment":
                self._parse_deployment(doc)
            elif kind == "Service":
                self._parse_service(doc)

        return self.nodes, self.edges

    def _parse_deployment(self, doc: dict) -> None:
        metadata = doc.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace", "default")
        labels = metadata.get("labels", {})

        if not name:
            return

        spec = doc.get("spec", {})
        replicas = spec.get("replicas", 1)
        
        template = spec.get("template", {})
        template_spec = template.get("spec", {})
        containers = template_spec.get("containers", [])

        container_info = {}
        env_vars = {}
        
        if containers:
            main_container = containers[0]
            container_info = {
                "image": main_container.get("image"),
                "replicas": replicas,
                "namespace": namespace,
            }
            
            resources = main_container.get("resources", {})
            if resources:
                limits = resources.get("limits", {})
                requests = resources.get("requests", {})
                if limits.get("cpu"):
                    container_info["resource_limit_cpu"] = limits["cpu"]
                if limits.get("memory"):
                    container_info["resource_limit_memory"] = limits["memory"]
                if requests.get("cpu"):
                    container_info["resource_request_cpu"] = requests["cpu"]
                if requests.get("memory"):
                    container_info["resource_request_memory"] = requests["memory"]

            for env in main_container.get("env", []):
                env_name = env.get("name")
                env_value = env.get("value")
                if env_name and env_value:
                    env_vars[env_name] = env_value

        node = Node(
            id=f"service:{name}",
            type="service",
            name=name,
            properties={
                "team": labels.get("team"),
                "k8s_namespace": namespace,
                "k8s_replicas": replicas,
                **container_info,
            },
        )
        self._add_node(node)

        for key, value in env_vars.items():
            if "_URL" in key and value:
                target_name = self._extract_service_from_k8s_url(value)
                if target_name and target_name != name:
                    edge = Edge(
                        id=f"edge:{name}-calls-{target_name}",
                        type="calls",
                        source=f"service:{name}",
                        target=f"service:{target_name}",
                        properties={"via": "k8s_env"},
                    )
                    self._add_edge(edge)

    def _parse_service(self, doc: dict) -> None:
        metadata = doc.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace", "default")

        if not name:
            return

        spec = doc.get("spec", {})
        ports = spec.get("ports", [])
        
        port_info = None
        if ports:
            port_info = ports[0].get("port")

        for node in self.nodes:
            if node.name == name:
                if port_info:
                    node.properties["k8s_port"] = port_info
                node.properties["k8s_service"] = True
                break

    def _extract_service_from_k8s_url(self, url: str) -> str | None:
        patterns = [
            r"http://([^.]+)\.",
            r"://([^:/.]+)[.:]",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
