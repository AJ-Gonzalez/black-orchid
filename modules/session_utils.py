"""Session and preferences management for collaborative AI coding sessions.

Provides tools to maintain working preferences, session context, and
collaboration patterns between developers and AI coding partners.
"""

from pathlib import Path


def load_working_preferences():
    """Load working preferences from working_preferences.md.

    Reads the preferences file that defines how the AI should collaborate
    with the developer - communication style, technical preferences,
    workflow patterns, etc.

    Returns:
        str: Contents of working_preferences.md, or helpful message if not found

    Example:
        >>> prefs = load_working_preferences()
        >>> print(prefs)
        # Working Preferences
        ...
    """
    prefs_file = Path("working_preferences.md")

    if not prefs_file.exists():
        return (
            "No working_preferences.md file found. "
            "Create one to define your collaboration preferences.\n\n"
            "Example preferences:\n"
            "- Communication style (emoji usage, verbosity)\n"
            "- Technical preferences (OOP vs functional, frameworks)\n"
            "- Collaboration patterns (explain vs execute, ask vs assume)"
        )

    try:
        with open(prefs_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading preferences: {e}"


def save_working_preference(key, value):
    """Add or update a working preference.

    Appends a new preference to working_preferences.md in a simple
    key-value format. If the file doesn't exist, creates it.

    Args:
        key (str): Preference name/key
        value (str): Preference value

    Returns:
        dict: Success status and message

    Example:
        >>> save_working_preference("emoji_usage", "minimal")
        {'success': True, 'message': 'Preference saved: emoji_usage = minimal'}
    """
    prefs_file = Path("working_preferences.md")

    try:
        # Create file with header if it doesn't exist
        if not prefs_file.exists():
            with open(prefs_file, 'w', encoding='utf-8') as f:
                f.write("# Working Preferences\n\n")

        # Append the preference
        with open(prefs_file, 'a', encoding='utf-8') as f:
            f.write(f"- **{key}**: {value}\n")

        return {
            "success": True,
            "message": f"Preference saved: {key} = {value}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to save preference: {e}"
        }


def get_preference(key):
    """Quick lookup of a specific preference value.

    Searches working_preferences.md for a line containing the key
    and returns the associated value.

    Args:
        key (str): Preference key to look up

    Returns:
        str: Preference value if found, or message if not found

    Example:
        >>> get_preference("emoji_usage")
        'minimal'
    """
    prefs_file = Path("working_preferences.md")

    if not prefs_file.exists():
        return f"Preference '{key}' not found (no preferences file exists)"

    try:
        with open(prefs_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Simple search for the key in markdown format
        for line in content.split('\n'):
            if key.lower() in line.lower():
                # Try to extract value after colon
                if ':' in line:
                    value = line.split(':', 1)[1].strip()
                    return value

        return f"Preference '{key}' not found in working_preferences.md"

    except Exception as e:
        return f"Error looking up preference: {e}"
