# Black Orchid

Hot-reloadable MCP proxy server for custom Python tools.
Safe module loading using `importlib` (not `exec`). Auto-discovers tools from Python modules with collision detection.

Built for Claude Code primarily but should work with any other setup that accepts MCP.

It's basically a hackable scripting engine through an MCP server

Still highly experimental. Feedback and contributions are welcome!

## Features

- Hot-reloadable MCP proxy server
- Safe module loading (importlib, not exec)
- Auto-discovers tools from Python modules
- Collision detection for duplicate function names
- Public and private module support

## How It Works

- Scans `modules/` (public) and `private/modules/` (private) folders
- Loads all .py files as tools
- Each function in a module becomes an MCP tool
- Hot reload without restarting server
- Path validation and syntax checking for security

## Installation

`claude mcp add --transport stdio Black_Orchid python "absolute/path/to/black_orchid.py"`

Note: Requires absolute path to black_orchid.py

## Available Built-in Tools

**System Utils:**
- `get_os_info()` - cross-platform OS detection and system information

**Session Utils:**
- `load_working_preferences()` - load collaboration preferences
- `save_working_preference(key, value)` - save a preference
- `get_preference(key)` - lookup specific preference

**Session Memory:**
- `remember(key, value)` - store ephemeral data for current session
- `recall(key)` - retrieve stored data
- `forget(key)` - remove specific memory
- `list_memories()` - see all stored keys
- `clear_all_memories()` - clear all session memory

**Reload Tools:**
- `reload_all_modules()` - reload all modules from scratch
- `reload_module(module_name)` - reload specific module
- `list_rejected_modules()` - debug module loading issues

## Creating Your Own Modules

You can create modules and ahve your own custom utilities, wrap APIs, whatever you can imagine. 



1. Create a .py file in `modules/` folder
2. Write functions with docstrings
3. Call `reload_all_modules()` to load new tools
4. Functions become available as MCP tools

Example simple module:
```python
def hello_world():
    """Say hello to the world."""
    return "Hello, World!"
```

**Important Notes:**

**Helper Functions:** Functions starting with `_` (underscore) are treated as private helpers and won't be exposed as tools. Use this for internal utilities.

```python
def _helper_function():
    """This won't be exposed as a tool"""
    return "internal use only"

def public_tool():
    """This will be exposed"""
    result = _helper_function()
    return result
```

**Classes:** Classes are not directly exposed as tools. To expose class methods, instantiate the class and call methods in a function.

```python
class MyUtility:
    def do_something(self):
        return "result"

# Expose the class method as a tool
def use_my_utility():
    """Use MyUtility class"""
    util = MyUtility()
    return util.do_something()
```

## Module Structure

- `modules/` - public tools (committed to git)
- `private/modules/` - private tools (gitignored)
- Collision handling: automatic `_modulename` suffix when function names conflict

## Usage Examples

- List available tools: `list_proxy_tools()`
- Call a tool: `use_proxy_tool(tool_id, kwargs)`
- Reload after changes: `reload_all_modules()`
- Check rejected modules: `list_rejected_modules()`