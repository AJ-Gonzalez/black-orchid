"""
Black Orchid Configuration Management

Provides tools for managing public and private configuration files.
Public config (config.yaml) - for general settings and public modules
Private config (private/config.yaml) - for personal settings and private modules

Features:
- Hot-reloadable configs
- Nested key access via dot notation
- Thread-safe operations
- Graceful fallback if configs don't exist
"""

import yaml
from pathlib import Path
from typing import Any, Optional
import threading

# Determine base directory (black-orchid root)
BASE_DIR = Path(__file__).parent.parent
PUBLIC_CONFIG_PATH = BASE_DIR / "config.yaml"
PRIVATE_CONFIG_PATH = BASE_DIR / "private" / "config.yaml"

# Thread-safe config storage
_config_lock = threading.Lock()
_configs = {
    "public": {},
    "private": {}
}


def _load_yaml_file(path: Path) -> dict:
    """Load and parse a YAML file, return empty dict if file doesn't exist."""
    if not path.exists():
        return {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            return content if content is not None else {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {path}: {e}")
    except Exception as e:
        raise IOError(f"Error reading {path}: {e}")


def _save_yaml_file(path: Path, data: dict) -> None:
    """Save data to a YAML file."""
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        raise IOError(f"Error writing {path}: {e}")


def _get_nested_value(data: dict, key_path: str) -> Any:
    """
    Get value from nested dict using dot notation.
    Example: "paths.story_of_us" -> data["paths"]["story_of_us"]
    """
    keys = key_path.split(".")
    current = data

    for key in keys:
        if not isinstance(current, dict):
            raise KeyError(f"Cannot access '{key}' - parent is not a dict")
        if key not in current:
            raise KeyError(f"Key '{key_path}' not found in config")
        current = current[key]

    return current


def _set_nested_value(data: dict, key_path: str, value: Any) -> None:
    """
    Set value in nested dict using dot notation.
    Creates intermediate dicts as needed.
    Example: "paths.story_of_us" -> data["paths"]["story_of_us"] = value
    """
    keys = key_path.split(".")
    current = data

    # Navigate to parent of final key, creating dicts as needed
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            raise ValueError(f"Cannot set '{key_path}' - '{key}' exists but is not a dict")
        current = current[key]

    # Set the final key
    current[keys[-1]] = value


def _initialize_configs() -> None:
    """Initialize configs from disk if not already loaded."""
    with _config_lock:
        if not _configs["public"]:
            _configs["public"] = _load_yaml_file(PUBLIC_CONFIG_PATH)
        if not _configs["private"]:
            _configs["private"] = _load_yaml_file(PRIVATE_CONFIG_PATH)


# Initialize configs on module load
_initialize_configs()


def get_config(scope: str = "public", key_path: Optional[str] = None) -> Any:
    """
    Read configuration value.

    Args:
        scope: "public" or "private"
        key_path: Dot-notation path to config value (e.g., "paths.story_of_us")
                  If None, returns entire config dict

    Returns:
        Configuration value or entire config dict

    Example:
        get_config("private", "paths.story_of_us")
        get_config("public")  # Returns entire public config
    """
    if scope not in ["public", "private"]:
        raise ValueError(f"Invalid scope '{scope}'. Must be 'public' or 'private'")

    with _config_lock:
        config = _configs[scope]

        if key_path is None:
            return config.copy()  # Return copy to prevent external modification

        try:
            return _get_nested_value(config, key_path)
        except KeyError as e:
            raise KeyError(f"Config key not found in {scope} config: {e}")


def set_config(scope: str, key_path: str, value: Any) -> str:
    """
    Update configuration value and save to disk.

    Args:
        scope: "public" or "private"
        key_path: Dot-notation path to config value (e.g., "paths.story_of_us")
        value: Value to set (can be any YAML-serializable type)

    Returns:
        Success message

    Example:
        set_config("private", "paths.story_of_us", "./private/story")
        set_config("public", "logging.level", "INFO")
    """
    if scope not in ["public", "private"]:
        raise ValueError(f"Invalid scope '{scope}'. Must be 'public' or 'private'")

    config_path = PUBLIC_CONFIG_PATH if scope == "public" else PRIVATE_CONFIG_PATH

    with _config_lock:
        # Update in-memory config
        _set_nested_value(_configs[scope], key_path, value)

        # Save to disk
        _save_yaml_file(config_path, _configs[scope])

    return f"✓ Updated {scope} config: {key_path} = {value}"


def reload_config(scope: Optional[str] = None) -> str:
    """
    Reload configuration from disk.

    Args:
        scope: "public", "private", or None (reload both)

    Returns:
        Success message

    Example:
        reload_config("private")  # Reload just private config
        reload_config()           # Reload both configs
    """
    if scope is not None and scope not in ["public", "private"]:
        raise ValueError(f"Invalid scope '{scope}'. Must be 'public', 'private', or None")

    scopes_to_reload = [scope] if scope else ["public", "private"]

    with _config_lock:
        for s in scopes_to_reload:
            config_path = PUBLIC_CONFIG_PATH if s == "public" else PRIVATE_CONFIG_PATH
            _configs[s] = _load_yaml_file(config_path)

    scope_msg = f"{scope} config" if scope else "both configs"
    return f"✓ Reloaded {scope_msg} from disk"


def get_config_paths() -> dict:
    """
    Get the paths to config files.

    Returns:
        Dict with "public" and "private" config file paths

    Example:
        paths = get_config_paths()
        print(paths["private"])  # C:/Users/.../black-orchid/private/config.yaml
    """
    return {
        "public": str(PUBLIC_CONFIG_PATH),
        "private": str(PRIVATE_CONFIG_PATH)
    }


def get_enabled_domains() -> list:
    """
    Get list of enabled domain names from both public and private configs.

    Merges domains from public and private configs, returning only enabled ones.
    This allows public config to define default domains while private config
    can add additional domains (like 'custom') that aren't in the public codebase.

    Returns:
        List of enabled domain names

    Example:
        >>> get_enabled_domains()
        ['technical', 'library', 'custom']
    """
    domains = []

    with _config_lock:
        # Get domains from public config
        public_domains = _configs["public"].get("domains", {})
        for domain_name, domain_config in public_domains.items():
            if isinstance(domain_config, dict) and domain_config.get("enabled", False):
                domains.append(domain_name)

        # Get domains from private config (if exists)
        private_domains = _configs["private"].get("domains", {})
        for domain_name, domain_config in private_domains.items():
            if isinstance(domain_config, dict) and domain_config.get("enabled", False):
                if domain_name not in domains:  # Avoid duplicates
                    domains.append(domain_name)

    return domains


def get_domain_config(domain_name: str) -> dict:
    """
    Get configuration for a specific domain.

    Checks private config first (takes precedence), then public config.

    Args:
        domain_name: Name of the domain to retrieve

    Returns:
        Domain configuration dict

    Raises:
        KeyError: If domain not found in either config

    Example:
        >>> get_domain_config("technical")
        {'enabled': True, 'description': 'Technical decisions...'}
    """
    with _config_lock:
        # Check private config first (takes precedence)
        private_domains = _configs["private"].get("domains", {})
        if domain_name in private_domains:
            return private_domains[domain_name].copy()

        # Check public config
        public_domains = _configs["public"].get("domains", {})
        if domain_name in public_domains:
            return public_domains[domain_name].copy()

        raise KeyError(f"Domain '{domain_name}' not found in config")


def is_domain_enabled(domain_name: str) -> bool:
    """
    Check if a domain is enabled.

    Args:
        domain_name: Name of the domain to check

    Returns:
        True if domain exists and is enabled, False otherwise

    Example:
        >>> is_domain_enabled("technical")
        True
        >>> is_domain_enabled("nonexistent")
        False
    """
    try:
        config = get_domain_config(domain_name)
        return config.get("enabled", False)
    except KeyError:
        return False
