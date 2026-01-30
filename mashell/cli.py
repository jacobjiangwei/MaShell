"""CLI argument parsing and main entry point."""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from mashell.agent.core import Agent
from mashell.config import get_config_path, load_config
from mashell.logo import display_logo
from mashell.session import SessionManager

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

    # Session management
    parser.add_argument(
        "-S", "--sessions",
        action="store_true",
        help="List all saved sessions",
    )
    parser.add_argument(
        "-r", "--resume",
        nargs="?",
        const="__MOST_RECENT__",
        metavar="N",
        help="Resume a session (most recent, or specify #N from list)",
    )
    parser.add_argument(
        "-s", "--session",
        metavar="NAME",
        help="Use or create a named session",
    )
    parser.add_argument(
        "-n", "--new-session",
        action="store_true",
        help="Force start a new session (don't resume)",
    )
    parser.add_argument(
        "--delete-session",
        metavar="NAME",
        help="Delete a saved session",
    )
    parser.add_argument(
        "--clear-sessions",
        action="store_true",
        help="Delete all saved sessions",
    )

    return parser.parse_args()


def show_sessions_list(console: Console, session_mgr: SessionManager) -> list:
    """Display a table of all saved sessions. Returns list of sessions."""
    from datetime import datetime

    sessions = session_mgr.list_sessions()

    if not sessions:
        console.print("[dim]No saved sessions found.[/dim]")
        console.print("\n[dim]Start a session with:[/dim]")
        console.print("  [cyan]mashell -s my-project \"your task here\"[/cyan]")
        return []

    # Sort by updated time, most recent first
    sessions.sort(key=lambda s: s.updated, reverse=True)

    table = Table(title="🗂️  Saved Sessions", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Last Active", style="dim")
    table.add_column("Task", max_width=40)

    def time_ago(iso_time: str) -> str:
        """Convert ISO time to human-readable 'time ago'."""
        try:
            dt = datetime.fromisoformat(iso_time)
            delta = datetime.now() - dt

            if delta.days > 7:
                return f"{delta.days // 7}w ago"
            elif delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m ago"
            else:
                return "just now"
        except (ValueError, TypeError):
            return "unknown"

    for i, sess in enumerate(sessions, 1):
        task = sess.original_task or "[no task]"
        if len(task) > 37:
            task = task[:37] + "..."
        table.add_row(
            str(i),
            sess.name,
            time_ago(sess.updated),
            task,
        )

    console.print(table)
    console.print()
    console.print("[dim]Usage:[/dim]")
    console.print("  [cyan]mashell --resume[/cyan]       Resume most recent (#1)")
    console.print("  [cyan]mashell --resume 2[/cyan]     Resume session #2")
    console.print("  [cyan]mashell -s NAME[/cyan]        Resume by name")

    return sessions


async def interactive_loop(
    agent: Agent,
    console: Console,
    session_mgr: SessionManager | None = None,
) -> None:
    """Run interactive conversation loop."""
    from pathlib import Path

    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory

    # Setup history file
    history_dir = Path.home() / ".mashell"
    history_dir.mkdir(exist_ok=True)
    history_file = history_dir / "history"

    prompt_session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_file))
    )

    console.print("[dim]Interactive mode. Type 'exit' or 'quit' to exit.[/dim]")
    console.print()

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt("You: ")
            )

            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            await agent.run(user_input)

            # Save session after each turn
            if session_mgr:
                session_mgr.update_from_context(agent.context, user_input)

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

    # Initialize session manager
    session_mgr = SessionManager()

    # Handle session management commands (don't need config)
    if args.sessions:
        show_sessions_list(console, session_mgr)
        return

    if args.delete_session:
        if session_mgr.delete(args.delete_session):
            console.print(f"[green]✓[/green] Deleted session: [bold]{args.delete_session}[/bold]")
        else:
            console.print(f"[yellow]Session not found:[/yellow] {args.delete_session}")
        return

    if args.clear_sessions:
        if Confirm.ask("[yellow]Delete all sessions?[/yellow]", default=False):
            count = session_mgr.clear_all()
            console.print(f"[green]✓[/green] Deleted {count} session(s)")
        return

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

    # Handle session resume
    session_name: str | None = None
    resume_prompt: str | None = None

    if args.resume:
        if args.resume == "__MOST_RECENT__":
            # Resume most recent session
            session = session_mgr.load_most_recent()
            if session:
                session_name = session.name
                resume_prompt = session_mgr.get_resume_prompt()
                console.print(f"[green]✓[/green] Resuming session: [bold]{session.name}[/bold]")
                if session.original_task:
                    task_preview = session.original_task[:60]
                    if len(session.original_task) > 60:
                        task_preview += "..."
                    console.print(f"[dim]  Task: {task_preview}[/dim]")
                console.print()
            else:
                console.print("[yellow]No sessions to resume.[/yellow]")
                console.print("[dim]Starting new session...[/dim]")
                console.print()
        else:
            # Resume by number
            try:
                idx = int(args.resume) - 1
                sessions = session_mgr.list_sessions()
                sessions.sort(key=lambda s: s.updated, reverse=True)
                if 0 <= idx < len(sessions):
                    session = session_mgr.load(sessions[idx].name)
                    if session:
                        session_name = session.name
                        resume_prompt = session_mgr.get_resume_prompt()
                        console.print(
                            f"[green]✓[/green] Resuming session: [bold]{session.name}[/bold]"
                        )
                        console.print()
                else:
                    console.print(f"[red]Invalid session number:[/red] {args.resume}")
                    show_sessions_list(console, session_mgr)
                    return
            except ValueError:
                # Treat as session name
                session = session_mgr.load(args.resume)
                if session:
                    session_name = session.name
                    resume_prompt = session_mgr.get_resume_prompt()
                    console.print(f"[green]✓[/green] Resuming session: [bold]{session.name}[/bold]")
                    console.print()
                else:
                    console.print(f"[yellow]Session not found:[/yellow] {args.resume}")
                    show_sessions_list(console, session_mgr)
                    return

    elif args.session:
        # Use or create named session
        session_name = args.session
        session = session_mgr.load(session_name)
        if session:
            resume_prompt = session_mgr.get_resume_prompt()
            console.print(f"[green]✓[/green] Resuming session: [bold]{session_name}[/bold]")
            console.print()
        else:
            session_mgr.create(name=session_name)
            console.print(f"[green]✓[/green] Created new session: [bold]{session_name}[/bold]")
            console.print()

    elif not args.new_session:
        # Check if there's a recent session to resume
        sessions = session_mgr.list_sessions()
        recent_session = None

        if sessions:
            # Find the most recent session with actual content
            sessions.sort(key=lambda s: s.updated, reverse=True)
            for sess in sessions:
                if sess.original_task:  # Has a task = has content worth resuming
                    recent_session = sess
                    break

        if recent_session:
            # Ask user if they want to resume
            task_preview = recent_session.original_task or ""
            if len(task_preview) > 50:
                task_preview = task_preview[:50] + "..."

            console.print(
                f"[cyan]📂 Found previous session:[/cyan] [bold]{recent_session.name}[/bold]"
            )
            console.print(f"[dim]   Task: {task_preview}[/dim]")
            console.print()

            choice = Prompt.ask(
                "Resume this session?",
                choices=["y", "n", "l"],
                default="y",
                show_choices=True,
            )
            console.print()

            if choice == "y":
                session = session_mgr.load(recent_session.name)
                if session:
                    session_name = session.name
                    resume_prompt = session_mgr.get_resume_prompt()
                    console.print(f"[green]✓[/green] Resuming session: [bold]{session.name}[/bold]")
                    console.print()
            elif choice == "l":
                # List all sessions
                show_sessions_list(console, session_mgr)
                console.print()
                session_choice = Prompt.ask(
                    "Enter session # or name (or press Enter for new)",
                    default=""
                )
                if session_choice:
                    try:
                        idx = int(session_choice) - 1
                        if 0 <= idx < len(sessions):
                            session = session_mgr.load(sessions[idx].name)
                            if session:
                                session_name = session.name
                                resume_prompt = session_mgr.get_resume_prompt()
                                console.print(
                                    f"[green]✓[/green] Resuming: [bold]{session.name}[/bold]"
                                )
                                console.print()
                    except ValueError:
                        # Treat as session name
                        session = session_mgr.load(session_choice)
                        if session:
                            session_name = session.name
                            resume_prompt = session_mgr.get_resume_prompt()
                            console.print(f"[green]✓[/green] Resuming: [bold]{session.name}[/bold]")
                            console.print()

                if not session_name:
                    # New session
                    session_name = "default"
                    session_mgr.create(name=session_name)
                    console.print("[green]✓[/green] Starting new session")
                    console.print()
            else:
                # Start fresh with default session
                session_name = "default"
                # Clear default session or create new
                session_mgr.create(name=session_name)
                console.print("[green]✓[/green] Starting new session")
                console.print()
        else:
            # No previous sessions - just create default
            session_name = "default"
            session = session_mgr.load(session_name)
            if not session:
                session_mgr.create(name=session_name)

    else:
        # --new-session: create a timestamped session
        from datetime import datetime
        session_name = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        session_mgr.create(name=session_name)
        console.print(f"[green]✓[/green] Created new session: [bold]{session_name}[/bold]")
        console.print()

    # Create agent
    agent = Agent(config, console)

    # Restore context from session if resuming
    if session_mgr.current:
        session_mgr.restore_to_context(agent.context)

    # Run
    if args.prompt:
        # Single prompt mode
        asyncio.run(agent.run(args.prompt))
        # Save session after single prompt
        session_mgr.update_from_context(agent.context, args.prompt)
    elif resume_prompt and not args.prompt:
        # Resuming - show what we're continuing
        console.print("[dim]─" * 50 + "[/dim]")
        console.print("[bold cyan]📋 Session Context:[/bold cyan]")
        for line in resume_prompt.split("\n")[:8]:  # Show first 8 lines
            console.print(f"[dim]  {line}[/dim]")
        console.print("[dim]─" * 50 + "[/dim]")
        console.print()
        # Enter interactive mode
        asyncio.run(interactive_loop(agent, console, session_mgr))
    else:
        # Interactive mode
        asyncio.run(interactive_loop(agent, console, session_mgr))


if __name__ == "__main__":
    main()
