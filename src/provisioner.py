import io
import os
import socket
import time
import sys
import base64
import click
from random import randint

import docker
import docker.errors

import config  # Specifies default values

client = docker.from_env()


def _find_available_port(starting_port: int, max_attempts: int = 50) -> int:
    """Scans the host machine for an available port."""
    for port in range(starting_port, starting_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                click.secho(
                    f"[*] Port {port} is busy, trying {port + 1}...", fg="yellow"
                )
                continue
    raise RuntimeError(f"Could not find an open port after {max_attempts} attempts.")


def _pull_image_with_progress(image_name: str):
    """
    Pulls a Docker image with a single-line CLI progress bar
    """

    try:
        client.images.get(image_name)

    except docker.errors.ImageNotFound:
        click.secho(
            f"[~] Image '{image_name}' not found locally. Pulling from registry...",
            fg="cyan",
        )

        try:
            for chunk in client.api.pull(image_name, stream=True, decode=True):
                # Isolate the progress bars and write over the current line
                if "progress" in chunk:
                    status = chunk.get("status", "")
                    progress = chunk.get("progress", "")
                    # \033[K clears the remainder of the line to prevent trailing artifacts
                    sys.stdout.write(f"\r\033[K  [~] {status}: {progress}")
                    sys.stdout.flush()
                elif "status" in chunk:
                    sys.stdout.write(f"\r\033[K  [~] {chunk['status']}")
                    sys.stdout.flush()
            sys.stdout.write("\n")

            click.secho(f"[✓] Successfully pulled {image_name}", fg="green")

        except docker.errors.APIError as e:
            click.secho(f"\n[!] Failed to pull image: {e}", fg="red", err=True)
            raise


def _build_dynamic_image(
    base_image: str,
    modifiers: list | dict,
    node_name: str,
    scenario_slug: str,
    is_supported_image: bool,
    quite: bool,
) -> str | docker.errors.BuildError:
    """Compiles a temporary Docker image in-memory scoped to a specific scenario."""
    target_tag = f"{config.GLOBAL_MANAGEMENT_LABEL}/{scenario_slug}-{node_name}"
    click.secho(f"[~] Compiling dynamic image layers for {target_tag}...", fg="cyan")

    dockerfile_lines = [f"FROM {base_image}"]

    if is_supported_image and isinstance(modifiers, dict):
        if "raw_instructions" in modifiers:
            dockerfile_lines.extend(modifiers["raw_instructions"])

        if "install_packages" in modifiers:
            pkgs = " ".join(modifiers["install_packages"])
            dockerfile_lines.extend(
                [
                    f"RUN apt-get update && apt-get install -y --no-install-recommends {pkgs} && rm -rf /var/lib/apt/lists/*",
                    f"RUN echo '{'\\n'.join(modifiers['install_packages'])}' >> /etc/{config.GLOBAL_MANAGEMENT_LABEL}_custom_tools.txt || true",
                ]
            )

        if "mkdir" in modifiers or "mkfile" in modifiers:
            dockerfile_lines.append("RUN mkdir -p /custom-cont-init.d && \\")
            dockerfile_lines.append(
                "    echo '#!/bin/bash' > /custom-cont-init.d/99-labod-runtime-setup.sh && \\"
            )

            if "mkdir" in modifiers:
                for d in modifiers["mkdir"]:
                    dockerfile_lines.append(
                        f"    echo 'mkdir -p \"{d}\"' >> /custom-cont-init.d/99-labod-runtime-setup.sh && \\"
                    )

            if "mkfile" in modifiers:
                for f in modifiers["mkfile"]:
                    path = f.get("path")
                    data = f.get("data", "")

                    # Base64 encoding mitigates bash string escaping vulnerabilities on injection
                    b64_data = base64.b64encode(data.encode("utf-8")).decode("utf-8")

                    dockerfile_lines.append(
                        f"    echo 'mkdir -p \"$(dirname {path})\"' >> /custom-cont-init.d/99-labod-runtime-setup.sh && \\"
                    )
                    dockerfile_lines.append(
                        f'    echo \'echo "{b64_data}" | base64 -d > "{path}"\' >> /custom-cont-init.d/99-labod-runtime-setup.sh && \\'
                    )

            # Finalize RUN block by making the init script executable
            dockerfile_lines.append(
                "    chmod +x /custom-cont-init.d/99-labod-runtime-setup.sh"
            )

    else:
        if isinstance(modifiers, list):
            dockerfile_lines.extend(modifiers)

        elif isinstance(modifiers, dict):
            click.secho(
                f"[!] Warning: {node_name} is generic but uses dictionary modifiers. Expecting a list of raw Dockerfile strings. Skipping.",
                fg="yellow",
                bold=True,
            )

    f_obj = io.BytesIO("\n".join(dockerfile_lines).encode("utf-8"))
    asset_labels = {
        "managed_by": config.GLOBAL_MANAGEMENT_LABEL,
        "scenario": scenario_slug,
    }

    try:
        build_stream = client.api.build(
            fileobj=f_obj,
            tag=target_tag,
            rm=True,
            forcerm=True,
            labels=asset_labels,
            decode=True,
        )

        if not quite:
            for chunk in build_stream:
                if "stream" in chunk:
                    log_line = chunk["stream"].strip()
                    if log_line:
                        click.secho(f"  [BUILD] {log_line}", fg="cyan", dim=True)
                elif "error" in chunk:
                    raise docker.errors.BuildError(chunk["error"], build_stream)

        return target_tag

    except docker.errors.BuildError as e:
        click.secho(
            f"[!] Dynamic image compilation failed for {target_tag}. Diagnostics:\n{e}",
            fg="red",
            err=True,
        )
        return e


def _create_networks(
    network_configs: list, scenario_slug: str, asset_labels: dict
) -> dict:
    """
    Provisions all Docker networks based on the YAML schema
    """

    if network_configs:
        created_networks = {}
        click.secho("[~] Provisioning Networks...", fg="cyan")
    else:
        return dict()

    for net_cfg in network_configs:
        net_name = f"{scenario_slug}_network_{net_cfg['name']}"
        net_driver = net_cfg.get("driver", "bridge")
        is_internal = net_cfg.get("internal", False)

        try:
            net_obj = client.networks.create(
                name=net_name,
                driver=net_driver,
                internal=is_internal,
                labels=asset_labels,
            )
            created_networks[net_cfg["name"]] = net_obj
            click.secho(
                f"[+] Created Network: {net_name} (Driver: {net_driver}, Internal: {is_internal})",
                fg="green",
            )
        except docker.errors.APIError as e:
            click.secho(
                f"[!] Error creating network {net_name}: {e}", fg="red", err=True
            )
            raise

    return created_networks


def _prepare_node_kwargs(
    node_data: dict,
    target_image: str,
    primary_net_name: str,
    scenario_slug: str,
    asset_labels: dict,
    is_defender: bool,
    is_supported_image: bool,
) -> dict:
    """Constructs the dictionary of arguments for client.containers.run()"""
    run_kwargs = {
        "image": target_image,
        "name": f"{scenario_slug}_{node_data['name']}",
        "network": primary_net_name,
        "detach": True,
        "labels": asset_labels,
    }

    # Capabilities
    cap_add = node_data.get("cap_add", [])
    cap_drop = node_data.get("cap_drop", [])
    _ = []

    if is_defender:
        for cap in config.DEFAULT_DEFENDER_CAPS:
            if cap not in cap_drop and cap not in cap_add:
                cap_add.append(cap)
                _.append(cap)
        if _:
            click.secho(f"[~] Auto-injecting required capability: {_}", fg="cyan")
        del _

    if cap_add:
        run_kwargs["cap_add"] = cap_add
    if cap_drop:
        run_kwargs["cap_drop"] = cap_drop

    if is_defender:
        requested_port = node_data.get("exposed_port", 8080)
        safe_port = _find_available_port(requested_port)
        run_kwargs["ports"] = {"3000/tcp": ("127.0.0.1", safe_port)}
        run_kwargs["shm_size"] = "512m"
        run_kwargs["_safe_port"] = safe_port

    if "exec_command" in node_data:
        run_kwargs["command"] = ["/bin/sh", "-c", node_data["exec_command"]]

    if "volumes" in node_data:
        resolved_volumes = []
        for vol in node_data["volumes"]:
            parts = vol.split(":")
            if parts[0].startswith("."):
                absolute_host_path = os.path.abspath(parts[0])
                resolved_vol = (
                    f"{absolute_host_path}:{parts[1]}:{parts[2]}"
                    if len(parts) == 3
                    else f"{absolute_host_path}:{parts[1]}"
                )
                resolved_volumes.append(resolved_vol)
            else:
                resolved_volumes.append(vol)
        run_kwargs["volumes"] = resolved_volumes

    run_kwargs["mem_limit"] = node_data.get("mem_limit", "1g")
    if not is_defender:
        run_kwargs["nano_cpus"] = int(node_data.get("cpus", 1.0) * 1e9)

    return run_kwargs


def _launch_node(
    node_data: dict,
    created_networks: dict,
    scenario_slug: str,
    asset_labels: dict,
    quite: bool,
    lab_context: dict,
    is_defender: bool = False,
):
    """
    Handles the lifecycle of provisioning a single container and attaching network
    """

    node_name = node_data["name"]
    base_img = node_data["base_image"]
    assigned_nets = node_data.get("networks", [])
    modifiers = node_data.get("build_modifiers")

    if not assigned_nets:
        click.secho(f"[!] Skipping {node_name}: No networks assigned.", fg="yellow")
        return

    is_supported_image = config.SUPPORTED_DEFENDER_IMAGE_PREFIX in base_img

    if is_supported_image:
        click.secho(f"[*] Supported Image Detected for: {node_name}", fg="yellow")

    _pull_image_with_progress(base_img)

    target_image = base_img
    if modifiers:
        target_image = _build_dynamic_image(
            base_img, modifiers, node_name, scenario_slug, is_supported_image, quite
        )

    if isinstance(target_image, docker.errors.BuildError):
        raise target_image

    primary_net_obj = created_networks[assigned_nets[0]]
    run_kwargs = _prepare_node_kwargs(
        node_data,
        target_image,
        primary_net_obj.name,
        scenario_slug,
        asset_labels,
        is_defender,
        is_supported_image,
    )

    safe_port = run_kwargs.pop("_safe_port", None)

    # Scrub hyphens so string.format(**kwargs) compiles correctly
    safe_node_name = node_name.replace("-", "_")
    node_context = {
        "mem_limit": run_kwargs.get("mem_limit", "N/A"),
        "cpus": node_data.get("cpus", 1.0),
        "networks": {},
    }

    try:
        container = client.containers.run(**run_kwargs)
        container.reload()

        if container.status != "running":
            click.secho(
                f"[!] Warning: {node_name} exited instantly. Check its command syntax.",
                fg="red",
                bold=True,
            )

        primary_ip = container.attrs["NetworkSettings"]["Networks"][
            primary_net_obj.name
        ].get("IPAddress", "Dead")

        # Write context properties
        node_context["ip"] = primary_ip
        node_context["networks"][assigned_nets[0]] = primary_ip

        click.secho(
            f"[✓] Launched {node_name} on {assigned_nets[0]} (IP: {primary_ip})",
            fg="green",
        )

        if is_supported_image and safe_port:
            node_context["port"] = safe_port
            click.secho(
                f"[✓] Workspace mapped: Access via http://127.0.0.1:{safe_port}",
                fg="magenta",
                bold=True,
            )

        if len(assigned_nets) > 1:
            for secondary_net in assigned_nets[1:]:
                secondary_net_obj = created_networks[secondary_net]
                secondary_net_obj.connect(container)
                container.reload()

                secondary_ip = container.attrs["NetworkSettings"]["Networks"][
                    secondary_net_obj.name
                ]["IPAddress"]

                # Append secondary network routing states
                node_context["networks"][secondary_net] = secondary_ip

                click.secho(
                    f" └── Attached to secondary network: {secondary_net} (IP: {secondary_ip})",
                    fg="cyan",
                )

    except docker.errors.APIError as e:
        click.secho(
            f"[!] Failed to launch {node_name}. Diagnostics:\n{e}", fg="red", err=True
        )

    # Save contextual state telemetry regardless of outcome
    lab_context[safe_node_name] = node_context


def launch_scenario(yaml_config: dict, quite: bool):
    """Main entrypoint orchestrator"""
    scenario_name = yaml_config.get(
        "scenario", config.GLOBAL_DEFAULT_SCENARIO_NAME + f"{randint(0, 100)}"
    )

    scenario_slug = scenario_name.lower().replace(" ", "_")
    lab_context = {}  # Global dict to track deployed telemetry

    asset_labels = {
        "managed_by": config.GLOBAL_MANAGEMENT_LABEL,
        "scenario": scenario_slug,
    }

    click.secho(f"[*] Deploying Scenario: {scenario_name}", fg="green", bold=True)

    network_configs = yaml_config.get("networks", [])
    created_networks = _create_networks(network_configs, scenario_slug, asset_labels)

    for node in yaml_config.get("nodes", []):
        _launch_node(
            node, created_networks, scenario_slug, asset_labels, quite, lab_context
        )

    if "defender_workspace" in yaml_config:
        _launch_node(
            yaml_config["defender_workspace"],
            created_networks,
            scenario_slug,
            asset_labels,
            quite,
            lab_context,
            is_defender=True,
        )

    if "attacker_node" in yaml_config:
        click.secho(
            "[~] Stabilizing environment... waiting 5 seconds before launching adversary.",
            fg="cyan",
            dim=True,
        )
        time.sleep(5)
        _launch_node(
            yaml_config["attacker_node"],
            created_networks,
            scenario_slug,
            asset_labels,
            quite,
            lab_context,
        )

    # Instructions Processing
    if "instructions" in yaml_config:
        raw_instructions = yaml_config["instructions"]
        click.secho("\n" + "=" * 50, fg="magenta", bold=True)
        click.secho(" LAB INSTRUCTIONS ".center(50), fg="magenta", bold=True)
        click.secho("=" * 50, fg="magenta", bold=True)

        try:
            formatted_instructions = raw_instructions.format(**lab_context)
            click.secho(f"\n{formatted_instructions}\n", fg="white", bold=True)
        except KeyError as e:
            click.secho(
                f"\n[!] Configuration Error: Variable {e} referenced in instructions was not found in parsed nodes.",
                fg="red",
                err=True,
            )
        except ValueError as e:
            click.secho(
                f"\n[!] String Formatting Error in instructions syntax: {e}",
                fg="red",
                err=True,
            )
