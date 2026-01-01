import yaml
import sys
import re
from pathlib import Path


class ConfigValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.services = set()
        self.teams = set()
        self.team_owned_services = {}

    def validate_all(self, data_dir: str = "data") -> bool:
        data_path = Path(data_dir)
        
        docker_compose_path = data_path / "docker-compose.yml"
        teams_path = data_path / "teams.yaml"
        k8s_path = data_path / "k8s-deployments.yaml"

        if docker_compose_path.exists():
            self.validate_docker_compose(docker_compose_path)
        else:
            self.errors.append(f"Missing required file: {docker_compose_path}")

        if teams_path.exists():
            self.validate_teams(teams_path)
        else:
            self.errors.append(f"Missing required file: {teams_path}")

        if k8s_path.exists():
            self.validate_kubernetes(k8s_path)

        self.cross_validate()

        return len(self.errors) == 0

    def validate_docker_compose(self, path: Path) -> None:
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in {path}: {e}")
            return

        if not data:
            self.errors.append(f"Empty docker-compose file: {path}")
            return

        services = data.get("services", {})
        if not services:
            self.errors.append("No services defined in docker-compose.yml")
            return

        for name, config in services.items():
            self.services.add(name)
            
            if not config:
                self.warnings.append(f"Service '{name}' has no configuration")
                continue

            if not config.get("image") and not config.get("build"):
                self.errors.append(f"Service '{name}' has no image or build specified")

            labels = config.get("labels", {})
            if isinstance(labels, list):
                labels = {l.split("=")[0]: l.split("=")[1] if "=" in l else "" for l in labels}
            
            team = labels.get("team")
            if team:
                if team not in self.team_owned_services:
                    self.team_owned_services[team] = []
                self.team_owned_services[team].append(name)

            depends_on = config.get("depends_on", [])
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())
            
            for dep in depends_on:
                if dep not in services:
                    self.errors.append(f"Service '{name}' depends on unknown service '{dep}'")

            env_vars = config.get("environment", [])
            if isinstance(env_vars, list):
                for env in env_vars:
                    if "=" in env:
                        key, value = env.split("=", 1)
                        self._validate_service_url(name, key, value, services)
            elif isinstance(env_vars, dict):
                for key, value in env_vars.items():
                    if value:
                        self._validate_service_url(name, key, str(value), services)

    def _validate_service_url(self, service: str, key: str, value: str, services: dict) -> None:
        url_pattern = r'http://([a-zA-Z0-9_-]+):\d+'
        matches = re.findall(url_pattern, value)
        for match in matches:
            if match not in services:
                self.warnings.append(
                    f"Service '{service}' references unknown service '{match}' in {key}"
                )

    def validate_teams(self, path: Path) -> None:
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in {path}: {e}")
            return

        if not data:
            self.errors.append(f"Empty teams file: {path}")
            return

        teams = data.get("teams", [])
        if not teams:
            self.errors.append("No teams defined in teams.yaml")
            return

        for team in teams:
            name = team.get("name")
            if not name:
                self.errors.append("Team missing 'name' field")
                continue
            
            self.teams.add(name)

            if not team.get("lead"):
                self.warnings.append(f"Team '{name}' has no lead defined")

            if not team.get("slack_channel"):
                self.warnings.append(f"Team '{name}' has no slack_channel defined")

            owns = team.get("owns", [])
            if not owns:
                self.warnings.append(f"Team '{name}' owns no services")

    def validate_kubernetes(self, path: Path) -> None:
        try:
            with open(path, 'r') as f:
                docs = list(yaml.safe_load_all(f))
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in {path}: {e}")
            return

        for doc in docs:
            if not doc:
                continue
            
            kind = doc.get("kind")
            metadata = doc.get("metadata", {})
            name = metadata.get("name")

            if kind == "Deployment":
                if not name:
                    self.errors.append("Deployment missing metadata.name")
                    continue

                spec = doc.get("spec", {})
                replicas = spec.get("replicas")
                if replicas is None:
                    self.warnings.append(f"Deployment '{name}' has no replicas specified")

                template = spec.get("template", {})
                containers = template.get("spec", {}).get("containers", [])
                if not containers:
                    self.errors.append(f"Deployment '{name}' has no containers defined")

            elif kind == "Service":
                if not name:
                    self.errors.append("Service missing metadata.name")

    def cross_validate(self) -> None:
        for team, services in self.team_owned_services.items():
            if team not in self.teams:
                self.warnings.append(
                    f"Team '{team}' referenced in docker-compose but not defined in teams.yaml"
                )

        for team_name in self.teams:
            if team_name not in self.team_owned_services:
                pass

    def print_report(self) -> None:
        print("\n" + "=" * 60)
        print("CONFIG VALIDATION REPORT")
        print("=" * 60)
        
        print(f"\nServices found: {len(self.services)}")
        print(f"Teams found: {len(self.teams)}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ All configurations are valid!")
        elif not self.errors:
            print("\n✅ No critical errors found.")
        
        print("\n" + "=" * 60)


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    
    validator = ConfigValidator()
    is_valid = validator.validate_all(data_dir)
    validator.print_report()
    
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
