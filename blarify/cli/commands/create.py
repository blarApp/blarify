"""Create command for building graphs from repositories."""

import asyncio
import json
import os
import secrets
import string
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Dict, Optional

from blarify.cli.project_config import ProjectConfig

from neo4j_container_manager import (
    Neo4jContainerManager,
    Neo4jContainerConfig,
    Environment,
    Neo4jContainerInstance,
    PortAllocation,
    VolumeInfo,
    ContainerStatus,
)
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.graph_environment import GraphEnvironment
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager
from blarify.documentation.documentation_creator import DocumentationCreator
from blarify.documentation.workflow_creator import WorkflowCreator
from blarify.agents.llm_provider import LLMProvider


def generate_neo4j_password() -> str:
    """Generate a secure random password for Neo4j (min 8 chars)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def get_or_create_neo4j_credentials() -> Dict[str, str]:
    """Get existing or create new Neo4j credentials."""
    creds_file = Path.home() / ".blarify" / "neo4j_credentials.json"
    creds_file.parent.mkdir(exist_ok=True)

    if creds_file.exists():
        with open(creds_file) as f:
            return json.load(f)
    else:
        creds = {"username": "neo4j", "password": generate_neo4j_password()}
        with open(creds_file, "w") as f:
            json.dump(creds, f)
        creds_file.chmod(0o600)
        return creds


def store_neo4j_credentials(creds: Dict[str, str]) -> None:
    """Store Neo4j credentials securely."""
    creds_file = Path.home() / ".blarify" / "neo4j_credentials.json"
    creds_file.parent.mkdir(exist_ok=True)
    with open(creds_file, "w") as f:
        json.dump(creds, f, indent=2)
    creds_file.chmod(0o600)


def display_neo4j_connection_info(uri: str, username: str, password: str, is_new: bool) -> None:
    """Display Neo4j connection information to user."""
    console = Console()

    # Extract port from URI for browser URL
    port = uri.split(":")[-1]
    bolt_port = int(port) if port.isdigit() else 7687
    http_port = bolt_port - 200 if bolt_port > 7687 else 7474  # Standard Neo4j port mapping

    if is_new:
        console.print(f"""
╔════════════════════════════════════════════════╗
║  Neo4j Container Started                       ║
╠════════════════════════════════════════════════╣
║  URI:      {uri:<36} ║
║  Browser:  http://localhost:{http_port:<18} ║
║  Username: {username:<36} ║
║  Password: {password:<36} ║
╠════════════════════════════════════════════════╣
║  Container will persist after exit            ║
║  To stop: blarify create --stop-neo4j         ║
╚════════════════════════════════════════════════╝
""")
    else:
        console.print(f"""
╔════════════════════════════════════════════════╗
║  Using Existing Neo4j Container               ║
╠════════════════════════════════════════════════╣
║  URI:      {uri:<36} ║
║  Browser:  http://localhost:{http_port:<18} ║
║  Username: {username:<36} ║
║  Password: {password:<36} ║
╚════════════════════════════════════════════════╝
""")


async def get_existing_container(manager: Neo4jContainerManager) -> Optional[Neo4jContainerInstance]:
    """Try to get an existing container."""
    try:
        containers = getattr(manager, "_running_containers", {})
        if "blarify-neo4j-dev" in containers:
            container = containers["blarify-neo4j-dev"]
            if await container.is_running():
                return container
    except Exception:
        pass

    # Try via Docker directly
    try:
        import docker

        client = docker.from_env()
        container = client.containers.get("blarify-neo4j-dev")
        if container.status == "running":
            # Get the actual port mappings from the running container
            port_bindings = container.attrs["NetworkSettings"]["Ports"]

            # Extract the actual mapped ports
            bolt_port = 7687  # Default
            http_port = 7474  # Default
            https_port = 7473  # Default

            if "7687/tcp" in port_bindings and port_bindings["7687/tcp"]:
                bolt_port = int(port_bindings["7687/tcp"][0]["HostPort"])

            if "7474/tcp" in port_bindings and port_bindings["7474/tcp"]:
                http_port = int(port_bindings["7474/tcp"][0]["HostPort"])

            if "7473/tcp" in port_bindings and port_bindings["7473/tcp"]:
                https_port = int(port_bindings["7473/tcp"][0]["HostPort"])

            # Create a proper Neo4jContainerInstance for the existing container
            creds = get_or_create_neo4j_credentials()

            # Create config for the existing container
            config = Neo4jContainerConfig(
                environment=Environment.DEVELOPMENT,
                password=creds["password"],
                username="neo4j",
                neo4j_version="5.25.1",  # We assume the version
                plugins=["apoc", "graph-data-science"],
            )

            # Create port allocation with actual ports
            ports = PortAllocation(bolt_port=bolt_port, http_port=http_port, https_port=https_port)

            # Create volume info
            volume = VolumeInfo(
                name="blarify-neo4j-dev-data",
                mount_path="/data",
                cleanup_on_stop=False,  # Development container persists
            )

            # Create the instance
            instance = Neo4jContainerInstance(
                config=config,
                container_id="blarify-neo4j-dev",
                ports=ports,
                volume=volume,
                status=ContainerStatus.RUNNING,
                container_ref=container,
            )

            return instance
    except Exception:
        pass

    return None


async def spawn_or_get_neo4j_container() -> Neo4jContainerInstance:
    """Spawn new or get existing Neo4j container."""
    manager = Neo4jContainerManager()

    # Try to get existing container
    existing = await get_existing_container(manager)
    if existing:
        # Password is already loaded in get_existing_container
        display_neo4j_connection_info(
            uri=existing.uri, username=existing.config.username, password=existing.config.password, is_new=False
        )
        return existing

    # Create new container
    creds = get_or_create_neo4j_credentials()
    config = Neo4jContainerConfig(
        environment=Environment.DEVELOPMENT,
        password=creds["password"],
        username="neo4j",
        neo4j_version="5.25.1",
        plugins=["apoc", "graph-data-science"],
        custom_config={
            "dbms.security.procedures.unrestricted": "apoc.*,gds.*",
            "dbms.security.procedures.allowlist": "apoc.*,gds.*",
        },
    )

    instance = await manager.start(config)
    display_neo4j_connection_info(uri=instance.uri, username=creds["username"], password=creds["password"], is_new=True)
    return instance


def should_spawn_neo4j(args: Namespace) -> bool:
    """Check if Neo4j container should be spawned."""
    # Check if Neo4j args are provided (not empty)
    has_uri = bool(args.neo4j_uri)
    has_username = bool(args.neo4j_username)
    has_password = bool(args.neo4j_password)

    # Only spawn if no configuration is provided
    # All three must be provided for manual configuration
    return not (has_uri and has_username and has_password)


def add_arguments(parser: ArgumentParser) -> None:
    """Add arguments for the create command.

    Args:
        parser: ArgumentParser to add arguments to
    """
    # Required arguments
    parser.add_argument("--entity-id", required=True, help="Entity identifier (e.g., company or organization name)")

    # Optional arguments
    parser.add_argument("--repo-id", help="Repository identifier (defaults to the repository path)")
    parser.add_argument("--docs", action="store_true", help="Generate documentation using LLM (requires API key)")
    parser.add_argument("--workflows", action="store_true", help="Discover and generate workflows")

    # LLM configuration (optional - for documentation generation)
    parser.add_argument(
        "--openai-api-key", help="OpenAI API key for documentation generation (overrides environment keys)"
    )
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "anthropic", "google"],
        default="openai",
        help="LLM provider to use for documentation generation",
    )

    # Neo4j configuration (optional - will auto-spawn container if not provided)
    parser.add_argument(
        "--neo4j-uri",
        help="Neo4j database URI (auto-spawns container if not provided)",
    )
    parser.add_argument("--neo4j-username", help="Neo4j username")
    parser.add_argument("--neo4j-password", help="Neo4j password")

    # Graph building options
    parser.add_argument(
        "--extensions-to-skip",
        nargs="+",
        default=[".json", ".xml", ".md", ".txt"],
        help="File extensions to skip during analysis",
    )
    parser.add_argument(
        "--names-to-skip",
        nargs="+",
        default=["__pycache__", "node_modules", ".git", "venv", ".venv"],
        help="File/folder names to skip during analysis",
    )
    parser.add_argument("--only-hierarchy", action="store_true", help="Build only the hierarchy without LSP analysis")

    # Documentation options
    parser.add_argument(
        "--max-workers", type=int, default=5, help="Maximum number of worker threads for documentation generation"
    )


def execute(args: Namespace) -> int:
    """Execute the create command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    console = Console()

    # Use current working directory as the repository path
    repo_path = os.getcwd()

    # Validate repository path
    if not os.path.exists(repo_path):
        console.print(f"[red]Error:[/red] Repository path does not exist: {repo_path}")
        return 1

    if not os.path.isdir(repo_path):
        console.print(f"[red]Error:[/red] Path is not a directory: {repo_path}")
        return 1

    # Use path as repo_id if not specified
    repo_id = args.repo_id or os.path.abspath(repo_path)

    # Check for API key if documentation is requested
    api_key = None
    if args.docs:
        # Priority: CLI argument > Environment variable(s)
        api_key = getattr(args, "openai_api_key", None)

        # If no CLI argument provided, check if any OpenAI keys exist in environment
        if not api_key:
            from blarify.agents.utils import discover_keys_for_provider

            discovered_keys = discover_keys_for_provider("openai")

            if not discovered_keys:
                console.print("[red]Error:[/red] OpenAI API key is required for documentation generation")
                console.print("You can provide it in one of these ways:")
                console.print("  1. [bold]Single key (env var):[/bold] export OPENAI_API_KEY=your-api-key")
                console.print("  2. [bold]Multiple keys for rotation:[/bold]")
                console.print("     export OPENAI_API_KEY=your-first-key")
                console.print("     export OPENAI_API_KEY_1=your-second-key")
                console.print("     export OPENAI_API_KEY_2=your-third-key")
                console.print("  3. [bold]CLI argument:[/bold] --openai-api-key your-api-key")
                console.print("  4. [bold]Set it now:[/bold]", end=" ")

                # Optional: Interactive prompt as fallback
                try:
                    import getpass

                    api_key = getpass.getpass("Enter your OpenAI API key: ").strip()
                    if not api_key:
                        return 1
                except (KeyboardInterrupt, EOFError):
                    console.print("\n[yellow]Documentation generation cancelled.[/yellow]")
                    return 1
            else:
                console.print(f"[green]✓[/green] Found {len(discovered_keys)} OpenAI API key(s) for rotation")

    # Check if we need to spawn Neo4j container
    if should_spawn_neo4j(args):
        try:
            # Handle async container spawn
            # asyncio.run() will fail if there's already an event loop running
            # This happens in tests with pytest-asyncio
            try:
                # Try asyncio.run first (normal case)
                container_instance = asyncio.run(spawn_or_get_neo4j_container())
            except RuntimeError as e:
                if "already running" in str(e) or "cannot be called from a running event loop" in str(e):
                    # We're in an async context (like pytest-asyncio)
                    # Create a new event loop in a thread
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, spawn_or_get_neo4j_container())
                        container_instance = future.result()
                else:
                    raise

            args.neo4j_uri = container_instance.uri
            args.neo4j_username = container_instance.config.username
            args.neo4j_password = container_instance.config.password
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to start Neo4j container: {e}")
            console.print("Please ensure Docker is running or provide Neo4j connection details manually.")
            return 1

    # Initialize Neo4j database manager
    try:
        db_manager = Neo4jManager(
            uri=args.neo4j_uri,
            user=args.neo4j_username,
            password=args.neo4j_password,
            repo_id=repo_id,
            entity_id=args.entity_id,
        )
        # Create indexes silently after connection
        db_manager.create_indexes()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to connect to database: {e}")
        return 1

    # Start building process
    console.print("\n[bold blue]Blarify Graph Builder[/bold blue]")
    console.print(f"Repository: [green]{repo_path}[/green]")
    console.print(f"Entity ID: [cyan]{args.entity_id}[/cyan]")
    console.print(f"Repo ID: [cyan]{repo_id}[/cyan]\n")

    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        try:
            # Phase 1: Build the graph
            task = progress.add_task("Building code graph...", total=None)

            graph_environment = GraphEnvironment(
                environment=args.entity_id,  # environment parameter name
                diff_identifier="0",  # diff_identifier parameter name
                root_path=repo_path,
            )

            builder = GraphBuilder(
                root_path=repo_path,
                only_hierarchy=args.only_hierarchy,
                extensions_to_skip=args.extensions_to_skip,
                names_to_skip=args.names_to_skip,
                graph_environment=graph_environment,
            )

            graph = builder.build()
            nodes = graph.get_nodes_as_objects()
            relationships = graph.get_relationships_as_objects()

            progress.update(
                task, description=f"Built graph with {len(nodes)} nodes and {len(relationships)} relationships"
            )

            # Phase 2: Save to database
            progress.update(task, description="Saving to database...")
            db_manager.save_graph(nodes, relationships)
            progress.update(task, description="Graph saved to database")

            # Phase 3: Generate documentation if requested
            if args.docs:
                progress.update(task, description="Generating documentation...")

                # Temporarily set CLI-provided API key if specified (doesn't interfere with rotation)
                original_api_key = os.environ.get("OPENAI_API_KEY")
                temp_key_set = False

                try:
                    # If user provided a key via CLI, temporarily set it (this becomes the first key to try)
                    if hasattr(args, "openai_api_key") and args.openai_api_key:
                        os.environ["OPENAI_API_KEY"] = args.openai_api_key
                        temp_key_set = True
                    elif api_key:  # From interactive prompt
                        os.environ["OPENAI_API_KEY"] = api_key
                        temp_key_set = True

                    llm_provider = LLMProvider()
                    doc_creator = DocumentationCreator(
                        db_manager=db_manager,
                        agent_caller=llm_provider,
                        graph_environment=graph_environment,
                        max_workers=args.max_workers,
                    )

                    doc_result = doc_creator.create_documentation()

                    if doc_result.error:
                        console.print(
                            f"[yellow]Warning:[/yellow] Documentation generation encountered errors: {doc_result.error}"
                        )
                    else:
                        progress.update(
                            task, description=f"Generated {doc_result.total_nodes_processed} documentation nodes"
                        )

                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Documentation generation failed: {e}")

                finally:
                    # Restore original environment variable state (preserve rotation system)
                    if temp_key_set:
                        if original_api_key is not None:
                            os.environ["OPENAI_API_KEY"] = original_api_key
                        else:
                            os.environ.pop("OPENAI_API_KEY", None)

            # Phase 4: Generate workflows if requested
            if args.workflows:
                progress.update(task, description="Discovering workflows...")

                try:
                    workflow_creator = WorkflowCreator(db_manager=db_manager, graph_environment=graph_environment)

                    workflow_result = workflow_creator.discover_workflows(save_to_database=True)

                    if workflow_result.error:
                        console.print(
                            f"[yellow]Warning:[/yellow] Workflow discovery encountered errors: {workflow_result.error}"
                        )
                    else:
                        progress.update(task, description=f"Discovered {workflow_result.total_workflows} workflows")

                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Workflow discovery failed: {e}")

            # Complete
            progress.update(task, description="Complete!", completed=100)

        except Exception as e:
            console.print(f"\n[red]Error:[/red] Graph building failed: {e}")
            return 1
        finally:
            db_manager.close()

    # Save project configuration for MCP server
    try:
        ProjectConfig.save_project_config(
            repo_id=repo_id,
            entity_id=args.entity_id,
            neo4j_uri=args.neo4j_uri
        )
    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Failed to save project configuration: {e}")

    # Print summary
    elapsed_time = time.time() - start_time
    console.print(f"\n[green]✓[/green] Graph built successfully in {elapsed_time:.1f} seconds!")
    console.print(f"  • Nodes: [cyan]{len(nodes)}[/cyan]")
    console.print(f"  • Relationships: [cyan]{len(relationships)}[/cyan]")

    if args.docs:
        console.print("  • Documentation: [green]Generated[/green]")
    if args.workflows:
        console.print("  • Workflows: [green]Discovered[/green]")

    # Print next steps
    console.print("\n[bold]Next steps:[/bold]")
    console.print("1. Start the MCP server from this directory: [cyan]blarify-mcp[/cyan]")
    console.print(f"2. Or specify the project: [cyan]blarify-mcp --project {repo_id}[/cyan]")
    console.print("3. Use with Claude Desktop or other MCP clients\n")

    return 0
