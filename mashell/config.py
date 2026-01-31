"""Configuration loading and management."""

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProviderConfig:
    """LLM provider configuration."""

    provider: str  # openai, azure, anthropic, ollama
    url: str  # API endpoint
    key: str | None  # API key (None for local)
    model: str  # Model/deployment name


@dataclass
class PermissionConfig:
    """Permission rules configuration."""

    auto_approve: list[str] = field(default_factory=list)
    always_ask: list[str] = field(default_factory=lambda: ["shell", "run_background"])


@dataclass
class SlackConfig:
    """Slack integration configuration."""

    bot_token: str  # xoxb-xxx Bot User OAuth Token
    app_token: str  # xapp-xxx App-Level Token for Socket Mode
    respond_to_mentions_only: bool = False  # Only respond when @mentioned
    allowed_channels: list[str] = field(default_factory=list)  # Empty = all channels
    allowed_users: list[str] = field(default_factory=list)  # Empty = all users


@dataclass
class Config:
    """Main configuration."""

    provider: ProviderConfig
    permissions: PermissionConfig
    verbose: bool = False
    auto_approve_all: bool = False
    working_dir: str = field(default_factory=os.getcwd)
    slack: SlackConfig | None = None  # Optional Slack integration

    @property
    def system_info(self) -> str:
        """Get current system information."""
        return f"{platform.system()} {platform.release()}"


def get_config_path() -> Path:
    """Get the default config file path."""
    return Path.home() / ".mashell" / "config.yaml"


def get_last_profile_path() -> Path:
    """Get the path to the last used profile file."""
    return Path.home() / ".mashell" / ".last_profile"


def save_last_profile(profile_name: str) -> None:
    """Save the last used profile name."""
    path = get_last_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile_name)


def get_last_profile() -> str | None:
    """Get the last used profile name, or None if not set."""
    path = get_last_profile_path()
    if path.exists():
        return path.read_text().strip()
    return None


def load_default_permissions() -> PermissionConfig:
    """Load default permission settings."""
    return PermissionConfig(
        auto_approve=[],
        always_ask=["shell", "run_background"],
    )


def load_from_profile(profile_name: str, config_path: str | None = None) -> Config:
    """Load configuration from a named profile."""
    path = Path(config_path) if config_path else get_config_path()

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    profiles = data.get("profiles", {})
    if profile_name not in profiles:
        raise ValueError(f"Profile '{profile_name}' not found in config")

    profile = profiles[profile_name]

    # Expand environment variables in key
    key = profile.get("key")
    if key and key.startswith("${") and key.endswith("}"):
        env_var = key[2:-1]
        key = os.getenv(env_var)

    # Load Slack config if present
    slack_config = _load_slack_config(profile.get("slack"))

    return Config(
        provider=ProviderConfig(
            provider=profile["provider"],
            url=profile["url"],
            key=key,
            model=profile["model"],
        ),
        permissions=_load_permissions_from_data(data),
        verbose=False,
        auto_approve_all=False,
        slack=slack_config,
    )


def _load_permissions_from_data(data: dict[str, Any]) -> PermissionConfig:
    """Load permissions from config data."""
    perms = data.get("permissions", {})
    return PermissionConfig(
        auto_approve=perms.get("auto_approve", []),
        always_ask=perms.get("always_ask", ["shell", "run_background"]),
    )


def _load_slack_config(slack_data: dict[str, Any] | None) -> SlackConfig | None:
    """Load Slack configuration from profile data."""
    if not slack_data:
        return None

    # Support environment variables for tokens
    bot_token = slack_data.get("bot_token", "")
    if bot_token.startswith("${") and bot_token.endswith("}"):
        bot_token = os.getenv(bot_token[2:-1], "")

    app_token = slack_data.get("app_token", "")
    if app_token.startswith("${") and app_token.endswith("}"):
        app_token = os.getenv(app_token[2:-1], "")

    if not bot_token or not app_token:
        return None

    return SlackConfig(
        bot_token=bot_token,
        app_token=app_token,
        respond_to_mentions_only=slack_data.get("respond_to_mentions_only", False),
        allowed_channels=slack_data.get("allowed_channels", []),
        allowed_users=slack_data.get("allowed_users", []),
    )


def load_config(
    provider: str | None = None,
    url: str | None = None,
    key: str | None = None,
    model: str | None = None,
    profile: str | None = None,
    config_path: str | None = None,
    verbose: bool = False,
    auto_approve_all: bool = False,
) -> Config:
    """
    Load configuration with priority: CLI args > env vars > config file.

    Auto-selects single profile if only one exists.
    """
    # If profile specified, load from config file
    if profile:
        config = load_from_profile(profile, config_path)
        config.verbose = verbose
        config.auto_approve_all = auto_approve_all
        save_last_profile(profile)  # Remember this profile
        return config

    # Build from CLI args / env vars
    resolved_provider = provider or os.getenv("MASHELL_PROVIDER")
    resolved_url = url or os.getenv("MASHELL_URL")
    resolved_key = key or os.getenv("MASHELL_KEY")
    resolved_model = model or os.getenv("MASHELL_MODEL")

    # If no CLI args or env vars, try to auto-load from config file
    if not any([resolved_provider, resolved_url, resolved_model]):
        path = Path(config_path) if config_path else get_config_path()
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
            profiles = data.get("profiles", {})

            if len(profiles) == 1:
                # Auto-select the only profile
                profile_name = list(profiles.keys())[0]
                config = load_from_profile(profile_name, config_path)
                config.verbose = verbose
                config.auto_approve_all = auto_approve_all
                save_last_profile(profile_name)
                return config
            elif len(profiles) > 1:
                # Multiple profiles - try to use last used profile
                last_profile = get_last_profile()
                if last_profile and last_profile in profiles:
                    config = load_from_profile(last_profile, config_path)
                    config.verbose = verbose
                    config.auto_approve_all = auto_approve_all
                    return config
                # No last profile or it's invalid - user must specify
                profile_names = ", ".join(profiles.keys())
                raise ValueError(
                    f"Multiple profiles found: {profile_names}. Use --profile to specify one."
                )

    # Validate required fields
    if not resolved_provider:
        raise ValueError("Provider is required. Use --provider or set MASHELL_PROVIDER")
    if not resolved_url:
        raise ValueError("URL is required. Use --url or set MASHELL_URL")
    if not resolved_model:
        raise ValueError("Model is required. Use --model or set MASHELL_MODEL")

    return Config(
        provider=ProviderConfig(
            provider=resolved_provider,
            url=resolved_url,
            key=resolved_key,
            model=resolved_model,
        ),
        permissions=load_default_permissions(),
        verbose=verbose,
        auto_approve_all=auto_approve_all,
    )


def add_auto_approve_tool(tool_name: str, config_path: str | None = None) -> None:
    """Add a tool to the auto_approve list in config file."""
    path = Path(config_path) if config_path else get_config_path()

    # Load existing config or create new
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Ensure permissions section exists
    if "permissions" not in data:
        data["permissions"] = {}

    if "auto_approve" not in data["permissions"]:
        data["permissions"]["auto_approve"] = []

    # Add tool if not already in list
    if tool_name not in data["permissions"]["auto_approve"]:
        data["permissions"]["auto_approve"].append(tool_name)

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save back to file
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
