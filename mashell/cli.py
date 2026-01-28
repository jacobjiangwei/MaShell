"""CLI argument parsing and main entry point."""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from mashell.agent.core import Agent
from mashell.config import get_config_path, load_config
from mashell.logo import display_logo

# Provider presets for easy configuration
PROVIDER_PRESETS = {
    "openai": {
        "url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "needs_key": True,
    },
    "azure": {
        "url": "",  # User must provide
        "default_model": "",  # User must provide deployment name
        "needs_key": True,
    },
    "anthropic": {
        "url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "needs_key": True,
    },
    "ollama": {
        "url": "http://localhost:11434",
        "default_model": "qwen2.5:14b",
        "needs_key": False,
    },
}


def run_init(console: Console) -> None:
    """Interactive configuration wizard."""
    import yaml

    console.print("\n[bold cyan]🐚 MaShell Configuration Wizard[/bold cyan]\n")
    console.print("Let's set up your AI provider configuration.\n")

    # Step 1: Choose provider
    console.print("[bold]Step 1:[/bold] Choose your LLM provider")
    console.print("  [dim]1.[/dim] openai    - OpenAI API (GPT-4o, etc.)")
    console.print("  [dim]2.[/dim] azure     - Azure OpenAI Service")
    console.print("  [dim]3.[/dim] anthropic - Anthropic API (Claude)")
    console.print("  [dim]4.[/dim] ollama    - Local Ollama (no API key needed)")
    console.print()

    provider = Prompt.ask(
        "Select provider",
        choices=["openai", "azure", "anthropic", "ollama", "1", "2", "3", "4"],
        default="openai"
    )

    # Map numbers to provider names
    provider_map = {"1": "openai", "2": "azure", "3": "anthropic", "4": "ollama"}
    provider = provider_map.get(provider, provider)

    preset = PROVIDER_PRESETS[provider]
    console.print(f"\n[green]✓[/green] Selected: [bold]{provider}[/bold]\n")

    # Step 2: API URL
    console.print("[bold]Step 2:[/bold] API Endpoint URL")
    if provider == "azure":
        console.print("  [dim]Example: https://your-resource.openai.azure.com/[/dim]")
        url = Prompt.ask("Enter your Azure OpenAI endpoint")
    elif preset["url"]:
        console.print(f"  [dim]Default: {preset['url']}[/dim]")
        url = Prompt.ask("API URL", default=str(preset["url"]))
    else:
        url = Prompt.ask("API URL")

    console.print(f"[green]✓[/green] URL: [bold]{url}[/bold]\n")

    # Step 3: API Key (if needed)
    key = None
    if preset["needs_key"]:
        console.print("[bold]Step 3:[/bold] API Key")
        console.print("  [dim]Your key will be saved securely in the config file.[/dim]")
        key = Prompt.ask("Enter your API key", password=True)
        console.print("[green]✓[/green] API key saved\n")
    else:
        console.print("[bold]Step 3:[/bold] API Key")
        console.print("  [dim]Not required for local models.[/dim]")
        console.print(f"[green]✓[/green] Skipped (not needed for {provider})\n")

    # Step 4: Model name
    console.print("[bold]Step 4:[/bold] Model / Deployment Name")
    if provider == "azure":
        console.print("  [dim]Enter your Azure deployment name (e.g., gpt-4o, gpt-35-turbo)[/dim]")
        model = Prompt.ask("Deployment name")
    elif preset["default_model"]:
        console.print(f"  [dim]Default: {preset['default_model']}[/dim]")
        model = Prompt.ask("Model name", default=str(preset["default_model"]))
    else:
        model = Prompt.ask("Model name")

    console.print(f"[green]✓[/green] Model: [bold]{model}[/bold]\n")

    # Step 5: Profile name
    console.print("[bold]Step 5:[/bold] Profile Name")
    console.print("  [dim]Save this configuration as a named profile for easy reuse.[/dim]")
    default_profile = provider
    profile_name = Prompt.ask("Profile name", default=default_profile)

    # Build config
    config_path = get_config_path()
    config_dir = config_path.parent

    # Load existing config or create new
    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
    else:
        config_data = {}

    # Ensure profiles section exists
    if "profiles" not in config_data:
        config_data["profiles"] = {}

    # Add/update profile
    config_data["profiles"][profile_name] = {
        "provider": provider,
        "url": url,
        "key": key,
        "model": model,
    }

    # Ensure permissions section exists with defaults
    if "permissions" not in config_data:
        config_data["permissions"] = {
            "auto_approve": [],
            "always_ask": ["shell", "run_background"],
        }

    # Save config
    config_dir.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

    console.print("\n[bold green]✅ Configuration saved![/bold green]")
    console.print(f"   Config file: [dim]{config_path}[/dim]")
    console.print(f"   Profile name: [bold]{profile_name}[/bold]")
    console.print()
    console.print("[bold]To use this profile:[/bold]")
    console.print(f"   [cyan]mashell --profile {profile_name} \"your prompt here\"[/cyan]")
    console.print()

    # Offer to test
    if Confirm.ask("Would you like to test the configuration now?", default=True):
        console.print("\n[dim]Testing connection...[/dim]")
        test_config(console, profile_name, config_path)


def test_config(console: Console, profile_name: str, config_path: Path) -> None:
    """Test a configuration profile."""
    try:
        config = load_config(profile=profile_name, config_path=str(config_path))

        # Create a simple test
        from mashell.providers import create_provider
        from mashell.providers.base import Message, Response

        provider = create_provider(
            config.provider.provider,
            config.provider.url,
            config.provider.key,
            config.provider.model,
        )

        async def do_test() -> Response:
            response = await provider.chat([
                Message(role="user", content="Say 'Hello from MaShell!' in exactly those words.")
            ])
            return response

        response = asyncio.run(do_test())

        if response.content:
            console.print("\n[bold green]✅ Connection successful![/bold green]")
            console.print(f"   Response: [italic]{response.content}[/italic]")
        else:
            console.print("\n[yellow]⚠️  Got empty response. Check your configuration.[/yellow]")

    except Exception as e:
        console.print(f"\n[red]❌ Connection failed:[/red] {e}")
        console.print("[dim]Please check your configuration and try again.[/dim]")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="mashell",
        description="🐚 MaShell - AI-powered command line assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mashell                                                         # Auto-starts setup if no config
  mashell init                                                    # Interactive setup wizard
  mashell --provider ollama --url http://localhost:11434 --model qwen2.5:14b "list files"
  mashell --profile azure "refactor this code"
  mashell -y "update all packages"                                # auto-approve mode
        """,
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="Task prompt or command (use 'init' for setup wizard)",
    )

    # Provider settings
    parser.add_argument(
        "--provider",
        help="LLM provider (openai, azure, anthropic, ollama)",
    )
    parser.add_argument(
        "--url",
        help="API endpoint URL",
    )
    parser.add_argument(
        "--key",
        help="API key (not needed for local models)",
    )
    parser.add_argument(
        "--model",
        help="Model name (or deployment name for Azure)",
    )

    # Config options
    parser.add_argument(
        "--profile",
        help="Use a saved profile from config file",
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to config file",
    )

    # Behavior options
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Auto-approve all commands (use with caution)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--no-logo",
        action="store_true",
        help="Skip the startup logo",
    )

    return parser.parse_args()


async def interactive_loop(agent: Agent, console: Console) -> None:
    """Run interactive conversation loop."""
    from pathlib import Path

    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    # Setup history file
    history_dir = Path.home() / ".mashell"
    history_dir.mkdir(exist_ok=True)
    history_file = history_dir / "history"

    session: PromptSession[str] = PromptSession(history=FileHistory(str(history_file)))

    console.print("[dim]Interactive mode. Type 'exit' or 'quit' to exit.[/dim]")
    console.print()

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt("You: ")
            )

            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            await agent.run(user_input)
            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit.[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break


def main() -> None:
    """Main entry point."""
    console = Console()
    args = parse_args()

    # Handle explicit init command
    if args.prompt == "init":
        if not args.no_logo:
            display_logo(console)
        run_init(console)
        return

    # Try to load config, auto-start onboarding if no config exists
    try:
        config = load_config(
            provider=args.provider,
            url=args.url,
            key=args.key,
            model=args.model,
            profile=args.profile,
            config_path=args.config,
            verbose=args.verbose,
            auto_approve_all=args.yes,
        )
    except ValueError as e:
        # No config provided - check if this is first run
        config_path = get_config_path()
        has_no_cli_args = not any([args.provider, args.url, args.model, args.profile])

        if has_no_cli_args and not config_path.exists():
            # First time user - start onboarding
            if not args.no_logo:
                display_logo(console)
            console.print("[yellow]No configuration found.[/yellow] Let's set up MaShell!\n")
            run_init(console)
            return
        else:
            # User tried to provide config but it's incomplete
            console.print(f"[red]Configuration error:[/red] {e}")
            console.print(
                "\n[dim]Run [bold]mashell init[/bold] for interactive setup, "
                "or use --help for options.[/dim]"
            )
            sys.exit(1)
    except FileNotFoundError as e:
        console.print(f"[red]Config file not found:[/red] {e}")
        console.print("\n[dim]Run [bold]mashell init[/bold] for interactive setup.[/dim]")
        sys.exit(1)

    # Display logo
    if not args.no_logo:
        display_logo(console)

    # Create agent
    agent = Agent(config, console)

    # Run
    if args.prompt:
        # Single prompt mode
        asyncio.run(agent.run(args.prompt))
    else:
        # Interactive mode
        asyncio.run(interactive_loop(agent, console))


if __name__ == "__main__":
    main()
