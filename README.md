
```
                                       __                               
_-_ _,,   ,,            ,,           ,-||-,              ,,        |\   
   -/  )  ||   _        ||          ('|||  )             ||     '   \\  
  ~||_<   ||  < \,  _-_ ||/\       (( |||--)) ,._-_  _-_ ||/\\ \\  / \\ 
   || \\  ||  /-|| ||   ||_<       (( |||--))  ||   ||   || || || || || 
   ,/--|| || (( || ||   || |        ( / |  )   ||   ||   || || || || || 
  _--_-'  \\  \/\\ \\,/ \\,\         -____-    \\,  \\,/ \\ |/ \\  \\/  
 (                                                         _/           
                                                                        
```
# Black Orchid: An Extendable Collaborative Environment Framework

Delivered as an MCP server, it allows dynamic creation of tools and skills for working with AI through Claude Code or any system that accepts MCP
It's a hot-reloadable MCP proxy server for custom Python tools, a hub for global (not project bound) skills. Uses safe module loading using`importlib` (not `exec`). And auto-discovers tools from Python modules with collision detection.


**Dynamic collaboration, hackable scripting, extensions on the fly**

Add your own skills, and use them with any project, add your own tools. 

This is both a collaborative space and a platform to extend capabilities. 

Still highly experimental. Feedback and contributions are welcome!

## Features

- Hot-reloadable MCP proxy server
- Safe module loading (importlib, not exec)
- Auto-discovers tools from Python modules
- Collision detection for duplicate function names
- Public and private module support
- Claude skills with auto discovery

## Installation

Please see `requirements.txt`, below are a couple ways to set it up.

### Quick setup:

`claude mcp add --transport stdio Black_Orchid python "absolute/path/to/black_orchid.py"`

Note: Requires absolute path to black_orchid.py and `fastmcp` installed globally, otherwise you will need to change the command. you will also need `python-toon` and `pyyaml`. This will only intall Black Orchid per folder. 

### For a global install: 

Please note Claude stores the GLOBAL MCP servers in a top level `mcpServers` property inside the `/Users/USERNAME/.claude.json`.

That is where you must add the command, and note you can use the fastmcp runner, UV, or simply run it with a venv you create if you wish to isolate dependencies.

## How It Works

Black Orchid lets you separate your skills, extension modules, and anything else into private and public folders, this is so if you fork the repo you can simply gitignore the private folder. Use this for personal things, sensitive data, etc. 

More publicly available default modules will continue to be added. 

For skills: 

- Scans `modules/skills/` (public) and `private/modules/skills` folders. 
- Lets Claude list the available skills 
- Embody skill: Claude has the skill and uses it
- Spawn agent: Claude sets up an agent with that skill then assigns them a task.

For tools:

- Scans `modules/` (public) and `private/modules/` (private) folders
- Loads all .py files as tools
- Each public function (not starting with `_`) in a module becomes an MCP tool
- Hot reload without restarting server
- Path validation and syntax checking for security


## Available Built-in Tools

### Working with Skills

*Skills are portable collaboration modes - ways of thinking and working that travel with you across projects.*

- `list_skills()` - see what modes are available (from both `modules/skills/` and `private/skills/`)
- `use_skill(skill_name)` - embody a skill in your current session
- `spawn_subagent_with_skill(skill_name, task)` - create a specialized agent with a skill as their context

*Want a new skill? Just create a markdown file in `modules/skills/` or `private/skills/` and call `reload_all_modules()`. Skills you create are immediately available.*

---

### Built-in Skills

Black Orchid comes with public skills to get you started:

**documentation-optimizer** - Transform verbose documentation into LLM-friendly, token-efficient markdown
- Marks human/AI scope boundaries clearly (🚫 human required, ✅ AI can handle, ⚠️ collaboration needed)
- Optimizes for token efficiency while preserving essential information
- Structures docs for quick lookup without repeated fetching
- Provides templates and guidelines for different doc types

*Especially useful when integrating new frameworks or APIs - fetch the docs once, optimize them, and reference them across sessions without re-fetching.*

**project-estimator** - Collaborative project scoping and time estimation
- Breaks down complex projects into estimable components
- Considers uncertainty and dependencies
- Provides ranges rather than false precision
- Helps surface hidden complexity early

*Use this when planning new features or projects - it helps turn "I want to build X" into "here's what X actually involves and how long it might take."*

**documentation-state-reviewer** - Systematic documentation auditing
- Examines actual code to understand what exists
- Reads current documentation
- Asks clarifying questions about intent and priorities
- Identifies gaps (features that exist but aren't documented)
- Identifies staleness (documentation that's outdated)
- Provides unbiased assessment of what needs updating

*Use this when you suspect your docs are out of sync with reality - it helps catch the gaps between "what we built" and "what we documented."*

---

### Managing Your Session

*Keep context alive across the conversation without bloating your context window.*

**Session Memory** (ephemeral - lives only in current session):
- `remember(key, value)` - store data for this session
- `recall(key)` - retrieve stored data
- `forget(key)` - remove specific memory
- `list_memories()` - see all stored keys
- `clear_all_memories()` - wipe the slate clean

**Working Preferences** (persistent - survives across sessions):
- `load_working_preferences()` - load your collaboration preferences
- `save_working_preference(key, value)` - save a preference for future sessions
- `get_preference(key)` - lookup specific preference

*Session memory is for "remember this API response for the next few turns." Preferences are for "I always want dark mode" or "my preferred code style is X."*

---

### System Information

*Know your environment so you can write cross-platform code.*

- `get_os_info()` - cross-platform OS detection and system information

*Returns platform, version, architecture - useful for conditional logic in your modules.*

---

### Hot Reloading & Debugging

*Made changes? See them instantly. Something broken? Find out why.*

- `reload_all_modules()` - reload all modules from scratch (tools and skills)
- `reload_module(module_name)` - reload just one specific module
- `list_rejected_modules()` - see which modules failed to load and why

*This is the magic - edit a Python file, call reload, and your changes are live. No server restart, no cache clearing, just instant feedback.*

## Creating Your Own Modules

You can create modules and have your own custom utilities, wrap APIs, whatever you can imagine.

Here's how:

1. Create a .py file in `modules/` folder
2. Write functions with docstrings
3. Call `reload_all_modules()` to load new tools
4. Functions become available as MCP tools

**Example simple module:**
```python
def hello_world():
    """Say hello to the world."""
    return "Hello, World!"
```

**Example with arguments:**
```python
def greet_person(name: str, enthusiasm: int = 5):
    """Greet a person with configurable enthusiasm.

    Args:
        name: The person's name
        enthusiasm: How many exclamation marks (default: 5)

    Returns:
        A greeting string
    """
    return f"Hello, {name}{'!' * enthusiasm}"
```

When called via Black Orchid: `use_proxy_tool("greet_person", {"name": "Alice", "enthusiasm": 3})` returns `"Hello, Alice!!!"`

**Error Handling:**
If a tool is called with incorrect arguments, Black Orchid returns a clear error message:
- Missing required argument: `"Error calling tool 'greet_person': missing required argument 'name'"`
- Wrong argument type: `"Error calling tool 'greet_person': argument 'enthusiasm' must be int, not str"`
- Unexpected argument: `"Error calling tool 'greet_person': unexpected keyword argument 'volume'"`

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

Contribution and feedback is always welcome. Skills, Tools, whatever you decide to add or create.
Thank you for reading, please tell me of any feature requests, bugs, or anything else. 

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