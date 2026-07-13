import yaml

from pathlib import Path


def parse_scenario(config_path: Path | str) -> dict:
    """
    Core parsing logic.
    Accepts a file path, loads the YAML, and returns the dictionary.
    """
    with open(config_path, "r") as stream:
        data = yaml.safe_load(stream)
        # scenario_name = data.get('scenario', 'Unnamed Scenario')
        # click.secho(f"[✓] Parsed configuration for: {scenario_name}", fg="green")
        return data
