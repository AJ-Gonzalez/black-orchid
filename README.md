# Black Orchid

```
    ____  __           __      ____            __    _     __
   / __ )/ /___ ______/ /__   / __ \__________/ /_  (_)___/ /
  / __  / / __ `/ ___/ //_/  / / / / ___/ ___/ __ \/ / __  /   Hackable scripting engine 
 / /_/ / / /_/ / /__/ ,<    / /_/ / /  / /__/ / / / / /_/ /   through an MCP server
/_____/_/\__,_/\___/_/|_|   \____/_/   \___/_/ /_/_/\__,_/   
                                                             
```

Hot-reloadable MCP proxy server for custom Python tools.
Safe module loading using `importlib` (not `exec`). Auto-discovers tools from Python modules with collision detection.

Built for Claude Code primarily but should work with any other setup that accepts MCP.

**It's basically a hackable scripting engine through an MCP server, you can add tools, scripts, etc.**

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

Note: Requires absolute path to black_orchid.py and `fastmcp` installed globally, otherwise you will need to change the command.

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

You can create modules and have your own custom utilities, wrap APIs, whatever you can imagine. 

Here's how:

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

### Talking to Claude Code

When you want Claude to use your Black Orchid tools, ask naturally:

```
"Using your Black Orchid proxy tools, can you call list_proxy_tools?"
```

Or more specifically:
```
"Please use the Black Orchid proxy tool 'get_os_info' to check my system"
```
If you already have mentioned Black Orchid you might not need to do much of this.

Claude will use the `use_proxy_tool` function automatically. You don't need to know the exact MCP function names - just reference "Black Orchid proxy tools" and describe what you want.

### Common Commands

- List available tools: `list_proxy_tools()`
- Call a tool: `use_proxy_tool(tool_id, kwargs)`
- Reload after changes: `reload_all_modules()`
- Check rejected modules: `list_rejected_modules()`

### Example Workflow

1. Create a new module in `modules/my_tools.py`
2. Ask Claude: "Using Black Orchid, reload all modules"
3. Ask Claude: "List the available Black Orchid proxy tools"
4. Ask Claude: "Use the my_function tool from Black Orchid"

## Security

Black Orchid is designed with security in mind, but follows a "trust but verify" approach:

**What it does:**
- Path validation: All module paths are validated against approved directories (`modules/` and `private/modules/`)
- Prevents directory traversal attacks - modules outside approved directories are rejected
- Safe module loading: Uses `importlib` (Python's standard module loader), **not `exec()`**
- Syntax validation: All modules are parsed with `ast.parse()` before loading to catch syntax errors
- Rejected modules tracking: Use `list_rejected_modules()` to see what failed to load and why

**What you should do/Best practices:**
- **Only load modules you trust** - Black Orchid executes Python code from your modules
- Review any modules before placing them in `modules/` or `private/modules/`
- Keep your `private/modules/` folder truly private (it's gitignored by default)
- Be cautious with third-party modules - verify the code before using

**Trust but verify:** You're ultimately responsible for what code you choose to load.

## Contributing

Contribution and feedback is always welcome. Thank you for reading, please tell me of any feature requests, bugs, or anything else. 

## Licensing stuff

 Copyright 2025 AJ Gonzalez

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.