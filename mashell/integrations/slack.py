"""Slack integration for MaShell - bidirectional communication via Socket Mode."""

import asyncio
import re
import threading
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console

if TYPE_CHECKING:
    from mashell.agent.core import Agent
    from mashell.config import SlackConfig
    from mashell.permissions.manager import PermissionRequest, PermissionResult

# Check if slack-bolt is installed
try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


def check_slack_available() -> None:
    """Check if Slack dependencies are installed."""
    if not SLACK_AVAILABLE:
        raise ImportError(
            "Slack dependencies not found. Try reinstalling mashell: pip install --upgrade mashell"
        )


class SlackPermissionUI:
    """Permission UI that prompts via Slack messages."""

    def __init__(self, client: "WebClient", console: Console | None = None) -> None:
        self.client = client
        self.console = console or Console()
        self._pending_responses: dict[str, str | None] = {}
        self._response_events: dict[str, threading.Event] = {}

    def set_response(self, thread_ts: str, response: str) -> None:
        """Set a response for a pending permission request."""
        if thread_ts in self._response_events:
            self._pending_responses[thread_ts] = response.strip().lower()
            self._response_events[thread_ts].set()

    async def prompt(
        self,
        request: "PermissionRequest",
        channel: str,
        thread_ts: str,
    ) -> "PermissionResult":
        """Display permission prompt via Slack and wait for user response."""
        from mashell.permissions.manager import PermissionResult

        # Format the permission request
        if "command" in request.arguments:
            cmd = request.arguments["command"]
            details = f"*Tool:* `{request.tool_name}`\n*Command:*\n```\n{cmd}\n```"
        else:
            args_str = "\n".join(f"  • {k}: `{v}`" for k, v in request.arguments.items())
            details = f"*Tool:* `{request.tool_name}`\n*Arguments:*\n{args_str}"

        message = (
            f"🔐 *Permission Request*\n\n"
            f"{details}\n\n"
            f"Reply with:\n"
            f"• `y` or `yes` - Approve\n"
            f"• `n` or `no` - Deny\n"
            f"• `a` or `always` - Always approve this tool"
        )

        # Send permission request to Slack
        self.client.chat_postMessage(
            channel=channel,
            text=message,
            thread_ts=thread_ts,
        )

        # Wait for response (with timeout)
        event = threading.Event()
        self._response_events[thread_ts] = event
        self._pending_responses[thread_ts] = None

        # Wait up to 60 seconds for response
        got_response = event.wait(timeout=60)

        response = self._pending_responses.pop(thread_ts, None)
        self._response_events.pop(thread_ts, None)

        if not got_response or response is None:
            self.client.chat_postMessage(
                channel=channel,
                text="⏰ Permission request timed out. Action denied.",
                thread_ts=thread_ts,
            )
            return PermissionResult(approved=False)

        if response in ("y", "yes"):
            return PermissionResult(approved=True)
        elif response in ("a", "always"):
            return PermissionResult(approved=True, remember=True)
        else:
            return PermissionResult(approved=False)


class SlackPermissionUIAdapter:
    """Adapter to make SlackPermissionUI compatible with PermissionUI interface."""

    def __init__(
        self,
        slack_ui: SlackPermissionUI,
        channel: str,
        thread_ts: str,
    ) -> None:
        self.slack_ui = slack_ui
        self.channel = channel
        self.thread_ts = thread_ts

    async def prompt(self, request: "PermissionRequest") -> "PermissionResult":
        """Prompt for permission via Slack."""
        return await self.slack_ui.prompt(request, self.channel, self.thread_ts)


class SlackBot:
    """
    Slack bot integration for MaShell.

    Provides bidirectional communication via Socket Mode:
    - Listens for messages from Slack users
    - Processes them through the MaShell agent
    - Sends responses back to Slack
    """

    def __init__(
        self,
        config: "SlackConfig",
        agent: "Agent",
        console: Console | None = None,
    ) -> None:
        """
        Initialize Slack bot.

        Args:
            config: Slack configuration with tokens
            agent: MaShell agent instance for processing messages
            console: Rich console for local logging
        """
        check_slack_available()

        self.config = config
        self.agent = agent
        self.console = console or Console()

        # Initialize Slack App with Bot Token
        self.app = App(token=config.bot_token)
        self.client: WebClient = self.app.client

        # Create Slack permission UI for permission prompts via Slack
        self._permission_ui = SlackPermissionUI(self.client, self.console)

        # Current conversation context for permission prompts
        self._current_channel: str | None = None
        self._current_thread_ts: str | None = None

        # Socket Mode handler for WebSocket connection
        self.handler = SocketModeHandler(self.app, config.app_token)

        # Get bot user ID for mention detection
        self._bot_user_id: str | None = None

        # Track active conversations (channel_id -> user context)
        self._conversations: dict[str, dict[str, Any]] = {}

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register Slack event handlers."""

        @self.app.event("message")
        def handle_message(event: dict[str, Any], say: Callable[..., Any]) -> None:
            """Handle incoming messages."""
            # Ignore bot messages (including our own)
            if event.get("bot_id") or event.get("subtype") == "bot_message":
                return

            # Ignore message edits and deletions
            if event.get("subtype") in ("message_changed", "message_deleted"):
                return

            channel = event.get("channel", "")
            user = event.get("user", "")
            text = event.get("text", "")
            thread_ts = event.get("thread_ts") or event.get("ts")

            # Check if this is a response to a permission request
            if thread_ts and thread_ts in self._permission_ui._response_events:
                self._permission_ui.set_response(thread_ts, text)
                return

            # Check channel restrictions
            if self.config.allowed_channels and channel not in self.config.allowed_channels:
                return

            # Check user restrictions
            if self.config.allowed_users and user not in self.config.allowed_users:
                return

            # If respond_to_mentions_only is enabled, skip here entirely
            # The app_mention event handler will handle @mentions
            if self.config.respond_to_mentions_only:
                return

            # Skip empty messages
            if not text.strip():
                return

            # Log the incoming message
            self.console.print(
                f"[bold cyan]Slack[/bold cyan] [dim]#{channel}[/dim] "
                f"[bold]@{user}:[/bold] {text[:100]}{'...' if len(text) > 100 else ''}"
            )

            # Process message through agent (run in new event loop for thread safety)
            asyncio.run(self._process_message(text, channel, user, thread_ts, say))

        @self.app.event("app_mention")
        def handle_mention(event: dict[str, Any], say: Callable[..., Any]) -> None:
            """Handle @mentions of the bot."""
            channel = event.get("channel", "")
            user = event.get("user", "")
            text = event.get("text", "")
            thread_ts = event.get("thread_ts") or event.get("ts")

            # Check if this is a response to a permission request
            parent_ts = event.get("thread_ts")
            if parent_ts and parent_ts in self._permission_ui._response_events:
                # Remove mention and check response
                clean_text = self._remove_mention(text)
                self._permission_ui.set_response(parent_ts, clean_text)
                return

            # Check restrictions
            if self.config.allowed_channels and channel not in self.config.allowed_channels:
                return
            if self.config.allowed_users and user not in self.config.allowed_users:
                return

            # Remove the mention from text
            text = self._remove_mention(text)

            if not text.strip():
                say(
                    text="Hi! How can I help you? Just mention me with your question.",
                    thread_ts=thread_ts,
                )
                return

            self.console.print(
                f"[bold cyan]Slack @mention[/bold cyan] [dim]#{channel}[/dim] "
                f"[bold]@{user}:[/bold] {text[:100]}{'...' if len(text) > 100 else ''}"
            )

            # Process message through agent (run in new event loop for thread safety)
            asyncio.run(self._process_message(text, channel, user, thread_ts, say))

    async def _process_message(
        self,
        text: str,
        channel: str,
        user: str,
        thread_ts: str,
        say: Callable[..., Any],
    ) -> None:
        """Process a message through the MaShell agent."""
        try:
            # Send typing indicator
            self._send_typing(channel)

            # Set current context for permission prompts
            self._current_channel = channel
            self._current_thread_ts = thread_ts

            # Create a custom permission UI that uses Slack
            original_ui = self.agent.permissions.ui
            self.agent.permissions.ui = SlackPermissionUIAdapter(
                self._permission_ui, channel, thread_ts
            )

            try:
                # Run the agent
                response = await self.agent.run(text)
            finally:
                # Restore original UI
                self.agent.permissions.ui = original_ui

            if response:
                # Split long messages (Slack limit is 4000 chars)
                messages = self._split_message(response)
                for msg in messages:
                    say(text=msg, thread_ts=thread_ts)
            else:
                say(
                    text="I processed your request but there's no response to show.",
                    thread_ts=thread_ts,
                )

        except Exception as e:
            error_msg = f"❌ Error processing request: {str(e)}"
            self.console.print(f"[red]{error_msg}[/red]")
            say(text=error_msg, thread_ts=thread_ts)

    def _send_typing(self, channel: str) -> None:
        """Send typing indicator to show bot is working."""
        try:
            # Note: Slack doesn't have a direct "typing" indicator for bots
            # We could post a temporary message or use reactions
            pass
        except Exception:
            pass

    def _is_mentioned(self, text: str) -> bool:
        """Check if the bot is mentioned in the text."""
        if not self._bot_user_id:
            self._fetch_bot_user_id()

        if self._bot_user_id:
            return f"<@{self._bot_user_id}>" in text
        return False

    def _remove_mention(self, text: str) -> str:
        """Remove bot mention from text."""
        if not self._bot_user_id:
            self._fetch_bot_user_id()

        if self._bot_user_id:
            # Remove the mention pattern
            text = re.sub(rf"<@{self._bot_user_id}>", "", text)

        return text.strip()

    def _fetch_bot_user_id(self) -> None:
        """Fetch the bot's user ID."""
        try:
            response = self.client.auth_test()
            self._bot_user_id = response.get("user_id")
        except SlackApiError as e:
            self.console.print(f"[yellow]Warning: Could not fetch bot user ID: {e}[/yellow]")

    def _split_message(self, text: str, max_length: int = 3900) -> list[str]:
        """Split a long message into chunks for Slack's message limit."""
        if len(text) <= max_length:
            return [text]

        messages = []
        current = ""

        # Try to split on newlines first
        lines = text.split("\n")

        for line in lines:
            if len(current) + len(line) + 1 > max_length:
                if current:
                    messages.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line

        if current:
            messages.append(current)

        return messages

    def send_message(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel ID or name (e.g., "#general" or "C1234567890")
            text: Message text to send
            thread_ts: Optional thread timestamp to reply in thread
        """
        try:
            self.client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts,
            )
        except SlackApiError as e:
            self.console.print(f"[red]Failed to send message: {e}[/red]")

    def start(self) -> None:
        """
        Start the Slack bot (blocking).

        This starts the Socket Mode WebSocket connection and listens for events.
        The method blocks until the bot is stopped.
        """
        self.console.print("[bold green]🤖 Starting Slack bot...[/bold green]")

        # Fetch bot user ID for mention detection
        self._fetch_bot_user_id()

        if self._bot_user_id:
            self.console.print(f"[dim]Bot user ID: {self._bot_user_id}[/dim]")

        self.console.print("[bold green]✅ Slack bot is running![/bold green]")
        self.console.print("[dim]Press Ctrl+C to stop.[/dim]")
        self.console.print()

        try:
            self.handler.start()
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopping Slack bot...[/yellow]")
            self.stop()

    def start_async(self) -> None:
        """
        Start the Slack bot in async mode (non-blocking).

        Use this when running alongside other async tasks.
        """
        self.console.print("[bold green]🤖 Starting Slack bot (async)...[/bold green]")
        self._fetch_bot_user_id()
        self.handler.connect()
        self.console.print("[bold green]✅ Slack bot connected![/bold green]")

    def stop(self) -> None:
        """Stop the Slack bot."""
        try:
            self.handler.close()
            self.console.print("[dim]Slack bot stopped.[/dim]")
        except Exception:
            pass


class SlackNotifier:
    """
    Simple Slack notifier for sending messages without full bot functionality.

    Use this when you only need to send messages, not receive them.
    """

    def __init__(self, bot_token: str, console: Console | None = None) -> None:
        """
        Initialize Slack notifier.

        Args:
            bot_token: Slack Bot User OAuth Token (xoxb-xxx)
            console: Optional Rich console for logging
        """
        check_slack_available()

        self.client = WebClient(token=bot_token)
        self.console = console or Console()

    def send(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> bool:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel ID or name
            text: Message text (fallback for notifications)
            thread_ts: Optional thread timestamp
            blocks: Optional Block Kit blocks for rich formatting

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            self.client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts,
                blocks=blocks,
            )
            return True
        except SlackApiError as e:
            self.console.print(f"[red]Failed to send Slack message: {e}[/red]")
            return False

    def send_file(
        self,
        channel: str,
        file_path: str,
        title: str | None = None,
        comment: str | None = None,
    ) -> bool:
        """
        Upload a file to a Slack channel.

        Args:
            channel: Channel ID or name
            file_path: Path to the file to upload
            title: Optional file title
            comment: Optional comment with the file

        Returns:
            True if uploaded successfully, False otherwise
        """
        try:
            self.client.files_upload_v2(
                channel=channel,
                file=file_path,
                title=title,
                initial_comment=comment,
            )
            return True
        except SlackApiError as e:
            self.console.print(f"[red]Failed to upload file: {e}[/red]")
            return False
