import click

from src.parser import parse_scenario

from src.provisioner import launch_scenario

from src.decommissioner import destruct
from src.decommissioner import destruct_built_images
from src.decommissioner import remove_depracted_nodes


@click.group()
def cli():
    """
    Universal Configuration-Driven Lab Orchestrator.
    """
    pass


@cli.command()
@click.argument(
    "config_path", type=click.Path(exists=True), required=True, default=None
)
@click.option(
    "-qb",
    "--quitebuild",
    is_flag=True,
    default=False,
    help="Disable Dynamic Build Logs",
)
def deploy(config_path, quitebuild):
    """
    Deploy isolated lab spaces dynamically from a single config
    """
    config_data = dict()

    try:
        click.secho(f"[~] Loading configuration profile from: {config_path}", fg="cyan")
        config_data = parse_scenario(config_path)
        click.secho(f"[✓] Parsed configuration for: {config_path}", fg="green")

    except Exception:
        click.secho("[!] Invalid yaml config file provided", fg="red", bold=True)
        return

    try:
        launch_scenario(config_data, quitebuild)
        click.secho(
            "\n[SUCCESS] Lab infrastructure is live!",
            fg="green",
            bold=True,
        )
    except Exception as e:
        click.secho(f"\n[ERROR] Deployment failed: {e}", fg="red", bold=True)

        remove_depracted_nodes(config_path)


@cli.command()
@click.argument(
    "config_path", type=click.Path(exists=True), required=False, default=None
)
def decommission(config_path):
    """
    Teardown running lab configurations and base images (Targeted or Global).
    """

    if config_path:
        # --- MODE 1: Targeted Teardown ---
        config_data = dict()
        try:
            click.secho(
                f"[~] Loading configuration profile from: {config_path}", fg="cyan"
            )
            config_data = parse_scenario(config_path)
            click.secho(f"[✓] Parsed configuration for: {config_path}", fg="green")

        except Exception:
            click.secho("[!] Invalid yaml config file provided", fg="red", bold=True)
            return

        # Containers first then underlying images
        destruct(yaml_config=config_data)

        click.secho(
            "\n[SUCCESS] Scenario environment purged cleanly.", fg="yellow", bold=True
        )

    else:
        # --- MODE 2: Global Teardown ---
        click.secho("⚠️  WARNING: No scenario file specified.", fg="red", bold=True)
        if click.confirm(
            "Do you want to perform a GLOBAL teardown and wipe all lab assets?"
        ):
            # Passing None triggers the global filter sweep
            destruct(yaml_config=None)
            click.secho(
                "\n[SUCCESS] Global environment wiped completely.",
                fg="yellow",
                bold=True,
            )
        else:
            click.echo("[*] Teardown aborted by user.")


# Standalone utility command if users only want to clean the image cache
@cli.command()
@click.argument(
    "config_path", type=click.Path(exists=True), required=False, default=None
)
def decommission_images(config_path):
    """
    Removes all custom built images by lab from the local Docker registry.
    """

    if config_path:
        config_data = dict()
        try:
            click.secho(
                f"[~] Loading configuration profile from: {config_path}", fg="cyan"
            )
            config_data = parse_scenario(config_path)
            click.secho(f"[✓] Parsed configuration for: {config_path}", fg="green")

        except Exception:
            click.secho("[!] Invalid yaml config file provided", fg="red", bold=True)
            return

        destruct_built_images(yaml_config=config_data)

        click.secho(
            "\n[SUCCESS] Scenario images purged cleanly.", fg="yellow", bold=True
        )
    else:
        # --- MODE 2: Global Image Teardown ---
        click.secho("⚠️  WARNING: No scenario file specified.", fg="red", bold=True)
        if click.confirm(
            "Do you want to perform a GLOBAL wipe of all custom built lab images?"
        ):
            destruct_built_images(yaml_config=None)
            click.secho(
                "\n[SUCCESS] Global image cache wiped cleanly.", fg="yellow", bold=True
            )
        else:
            click.echo("[*] Image teardown aborted by user.")


if __name__ == "__main__":
    cli()
