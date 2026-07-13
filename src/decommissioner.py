import docker
import docker.errors
import click

import config

from src.parser import parse_scenario

# Initialize Docker client
client = docker.from_env()


def remove_depracted_nodes(config_path):
    """
    Removes created nodes or networks deployed during failed scenario deployment
    """
    click.secho("[!] Removing Deployed Nodes and Networks", fg="yellow", dim=True)

    yaml_config = parse_scenario(config_path)

    filters = {"label": [config.GLOBAL_MANAGEMENT_LABEL_DOCKER]}

    scenario_slug = yaml_config.get("scenario", "unnamed").lower().replace(" ", "_")
    filters["label"].append(f"scenario={scenario_slug}")

    containers = client.containers.list(all=True, filters=filters)
    networks = client.networks.list(filters=filters)

    if not containers and not networks:
        click.secho("[*] None found", fg="yellow", dim=True)
        return

    for container in containers:
        click.secho(
            f"[-] Stopping and removing container: {container.name}...",
            fg="yellow",
            dim=True,
        )
        try:
            container.stop(timeout=2)
            # v=True ensures associated anonymous volumes are destroyed to prevent disk bloat
            container.remove(force=True, v=True)
        except docker.errors.APIError as e:
            click.secho(
                f"[!] Could not remove {container.name}: {e}", fg="red", err=True
            )

    networks = client.networks.list(filters=filters)
    for network in networks:
        click.secho(f"[-] Removing network: {network.name}...", fg="yellow", dim=True)
        try:
            network.remove()
        except docker.errors.APIError as e:
            click.secho(f"[!] Could not remove {network.name}: {e}", fg="red", err=True)


def destruct(yaml_config=None):
    """
    Tears down running infrastructure (Containers and Networks).
    If yaml_config is provided, it destroys ONLY that scenario.
    If yaml_config is None, it destroys EVERYTHING created by the platform excluding built images.
    """
    filters = {"label": [config.GLOBAL_MANAGEMENT_LABEL_DOCKER]}

    if yaml_config:
        scenario_slug = yaml_config.get("scenario", "unnamed").lower().replace(" ", "_")
        filters["label"].append(f"scenario={scenario_slug}")
        click.secho(
            f"\n=== Initiating Targeted Teardown for: {scenario_slug} ===",
            fg="yellow",
            bold=True,
        )
    else:
        click.secho("\n=== Initiating GLOBAL TEARDOWN ===", fg="red", bold=True)

    # 1. Terminate and Remove Containers
    containers = client.containers.list(all=True, filters=filters)
    networks = client.networks.list(filters=filters)

    if not containers and not networks:
        click.secho("[*] No active containers found matching criteria.", fg="cyan")
        return

    for container in containers:
        click.secho(
            f"[-] Stopping and removing container: {container.name}...", fg="yellow"
        )
        try:
            container.stop(timeout=2)
            # v=True ensures associated anonymous volumes are destroyed to prevent disk bloat
            container.remove(force=True, v=True)
        except docker.errors.APIError as e:
            click.secho(
                f"[!] Could not remove {container.name}: {e}", fg="red", err=True
            )

    # 2. Remove Networks
    for network in networks:
        click.secho(f"[-] Removing network: {network.name}...", fg="yellow")
        try:
            network.remove()
        except docker.errors.APIError as e:
            click.secho(f"[!] Could not remove {network.name}: {e}", fg="red", err=True)


def destruct_built_images(yaml_config=None):
    """
    Deletes dynamically compiled images.
    If yaml_config is provided, it destroys ONLY that scenario's images.
    If yaml_config is None, it destroys EVERY BUILT IMAGE created by the platform.
    """
    filters = {"label": [config.GLOBAL_MANAGEMENT_LABEL_DOCKER]}

    if yaml_config:
        scenario_slug = yaml_config.get("scenario", "unnamed").lower().replace(" ", "_")
        filters["label"].append(f"scenario={scenario_slug}")
        click.secho(
            f"\n=== Initiating Targeted Image Teardown for: {scenario_slug} ===",
            fg="yellow",
            bold=True,
        )
    else:
        click.secho("\n=== Initiating GLOBAL IMAGE TEARDOWN ===", fg="red", bold=True)

    # Fetch images matching the metadata labels
    try:
        images = client.images.list(filters=filters)
    except docker.errors.APIError as e:
        click.secho(
            f"[!] Failed to query Docker engine for images: {e}", fg="red", err=True
        )
        return

    if not images:
        click.secho(
            "[*] No dynamically built images found matching criteria.", fg="cyan"
        )
        return

    for image in images:
        # Images can have multiple tags, or none at all if they are dangling layers.
        # Safely extract a display name for the CLI UI.
        display_name = image.tags[0] if image.tags else image.short_id
        click.secho(f"[-] Deleting custom image layers: {display_name}...", fg="yellow")

        try:
            # force=True bypasses conflicts if an image is tagged in multiple repositories
            # noprune=False ensures we clean up the dangling, untagged parent layers
            client.images.remove(image.id, force=True, noprune=False)
        except docker.errors.APIError as e:
            click.secho(
                f"[!] Could not remove image {display_name}: {e}", fg="red", err=True
            )
