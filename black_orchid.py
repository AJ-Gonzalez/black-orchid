"""Black Orchid: Hot-reloadable MCP proxy server with collision detection/ Hackable scripting for MCP"""

from pathlib import Path
from typing import Any
from datetime import datetime
from importlib.util import spec_from_file_location, module_from_spec
import glob
import ast
import sys

from fastmcp import FastMCP
from toon import encode


# ProxyHandler: Dynamic module loading with collision detection
class ProxyHandler:
    """Proxy Handler class for loading python modules dynamically.

    Auto-discovers modules from:
    - modules/ (public, committed to git)
    - private/modules/ (private, gitignored) if it exists

    Validates all paths to prevent directory traversal attacks.
    """

    def __init__(self):
        """Initialize ProxyHandler with auto-discovery of module directories."""

        # Base directory (where black_orchid.py lives)
        self.base_dir = Path(__file__).parent.resolve()

        # Module directories to scan
        self.modules_dir = self.base_dir / "modules"
        self.private_modules_dir = self.base_dir / "private" / "modules"

        # Valid module directories (for path validation)
        self.valid_dirs = [self.modules_dir.resolve()]
        if self.private_modules_dir.exists():
            self.valid_dirs.append(self.private_modules_dir.resolve())

        # Registry structure: tool_name -> tool metadata
        self.registry = {}
        # Track original function names for collision detection
        self._name_tracker = {}  # original_name -> list of (module_name, final_tool_name)
        # Track rejected modules for debugging
        self.rejected_modules = []  # list of (path, reason) tuples

        # Discover modules from all valid directories
        self.raw_modules = []
        for valid_dir in self.valid_dirs:
            self.raw_modules.extend(glob.glob(str(valid_dir / "*.py")))

        self.okmods = []

        # Validate and check modules
        for mod in self.raw_modules:
            mod_path = Path(mod).resolve()

            is_valid_path = any(
                mod_path.is_relative_to(valid_dir)
                for valid_dir in self.valid_dirs
            )

            if not is_valid_path:
                self.rejected_modules.append((mod, "path_traversal_attempt"))
                continue

            if mod_path.stem == "toolset":
                continue

            try:
                with open(mod_path, "r", encoding="utf-8") as f:
                    source = f.read()
                    ast.parse(source)
                    self.okmods.append(str(mod_path))
            except SyntaxError:
                self.rejected_modules.append((mod, "syntax_error"))
            except Exception as e:
                self.rejected_modules.append((mod, f"read_error: {e}"))

        # Load modules and build registry with collision detection
        self.loaded_mods = {}
        for mod_path in self.okmods:
            mod_name = Path(mod_path).stem

            try:
                # Import the module from file path using importlib.util
                spec = spec_from_file_location(mod_name, mod_path)
                if spec is None or spec.loader is None:
                    continue

                tmod = module_from_spec(spec)
                sys.modules[mod_name] = tmod
                spec.loader.exec_module(tmod)
                self.loaded_mods[mod_name] = tmod

                # Extract toolable endpoints (functions)
                # Filter out dunder methods, non-lowercase, and underscore-prefixed helpers
                clean_list = [x for x in dir(tmod) if "__" not in x and x.islower() and not x.startswith('_')]

                # Register each function with collision detection
                for fn_name in clean_list:
                    self._register_tool(
                        original_name=fn_name,
                        module_name=mod_name,
                        function=getattr(tmod, fn_name)
                    )
            except Exception as e:
                # Track modules that fail to load due to import or other errors
                import traceback as tb
                error_details = ''.join(tb.format_exception(type(e), e, e.__traceback__))
                self.rejected_modules.append((mod_path, f"import_error: {str(e)}"))
                # Continue loading other modules
                continue

    def _register_tool(self, original_name: str, module_name: str, function: callable):
        """Register a tool with collision detection.

        If this is the first time seeing this function name, register it simply.
        If we've seen it before (collision), retroactively rename the first one
        and give this one a suffixed name too.
        """
        # Check if we've seen this function name before
        if original_name in self._name_tracker:
            # COLLISION DETECTED
            # Retroactively rename the first occurrence
            first_module, first_tool_name = self._name_tracker[original_name][0]

            # Only rename if it hasn't been renamed yet (still using original name)
            # AND the tool still exists in registry (might have been removed during reload)
            if first_tool_name == original_name and original_name in self.registry:
                new_first_name = f"{original_name}_{first_module}"
                # Move the registry entry
                self.registry[new_first_name] = self.registry.pop(original_name)
                self.registry[new_first_name]["had_collision"] = True
                # Update tracker
                self._name_tracker[original_name][0] = (first_module, new_first_name)

            # Register this new one with suffix
            new_tool_name = f"{original_name}_{module_name}"
            self.registry[new_tool_name] = {
                "function": function,
                "docstring": function.__doc__,
                "source_module": module_name,
                "original_name": original_name,
                "had_collision": True
            }
            # Track this collision
            self._name_tracker[original_name].append((module_name, new_tool_name))
        else:
            # First time seeing this name - register simply
            self.registry[original_name] = {
                "function": function,
                "docstring": function.__doc__,
                "source_module": module_name,
                "original_name": original_name,
                "had_collision": False
            }
            # Start tracking this name
            self._name_tracker[original_name] = [(module_name, original_name)]

    def use_proxy_tool(self, tool_id: str, kwargs: dict) -> Any:
        """Use proxy tool by ID with keyword arguments."""
        if tool_id not in self.registry:
            raise KeyError(f"Tool '{tool_id}' not found in registry. Available tools: {list(self.registry.keys())}")

        proxy_fn = self.registry[tool_id]["function"]
        return proxy_fn(**kwargs)

    def list_tools(self) -> dict:
        """List all registered tools with their docstrings."""
        return {name: info["docstring"] for name, info in self.registry.items()}

    def reload_all_modules(self) -> str:
        """Reload all modules from scratch. Rebuilds collision detection."""
        # Clear all state
        self.registry.clear()
        self._name_tracker.clear()
        self.loaded_mods.clear()
        self.rejected_modules.clear()

        # Re-discover modules
        self.raw_modules = []
        for valid_dir in self.valid_dirs:
            self.raw_modules.extend(glob.glob(str(valid_dir / "*.py")))

        self.okmods = []

        # Validate and check modules
        for mod in self.raw_modules:
            mod_path = Path(mod).resolve()

            is_valid_path = any(
                mod_path.is_relative_to(valid_dir)
                for valid_dir in self.valid_dirs
            )

            if not is_valid_path:
                self.rejected_modules.append((mod, "path_traversal_attempt"))
                continue

            if mod_path.stem == "toolset":
                continue

            try:
                with open(mod_path, "r", encoding="utf-8") as f:
                    source = f.read()
                    ast.parse(source)
                    self.okmods.append(str(mod_path))
            except SyntaxError:
                self.rejected_modules.append((mod, "syntax_error"))
            except Exception as e:
                self.rejected_modules.append((mod, f"read_error: {e}"))

        # Load modules
        for mod_path in self.okmods:
            mod_name = Path(mod_path).stem

            # Reload if already in sys.modules, otherwise load fresh
            if mod_name in sys.modules:
                try:
                    from importlib import reload
                    tmod = reload(sys.modules[mod_name])
                except Exception:
                    # If reload fails, try fresh import
                    spec = spec_from_file_location(mod_name, mod_path)
                    if spec is None or spec.loader is None:
                        continue
                    tmod = module_from_spec(spec)
                    sys.modules[mod_name] = tmod
                    spec.loader.exec_module(tmod)
            else:
                spec = spec_from_file_location(mod_name, mod_path)
                if spec is None or spec.loader is None:
                    continue
                tmod = module_from_spec(spec)
                sys.modules[mod_name] = tmod
                spec.loader.exec_module(tmod)

            self.loaded_mods[mod_name] = tmod

            # Register tools
            # Filter out dunder methods, non-lowercase, and underscore-prefixed helpers
            clean_list = [x for x in dir(tmod) if "__" not in x and x.islower() and not x.startswith('_')]
            for fn_name in clean_list:
                self._register_tool(
                    original_name=fn_name,
                    module_name=mod_name,
                    function=getattr(tmod, fn_name)
                )

        # Return summary
        num_tools = len(self.registry)
        num_modules = len(self.loaded_mods)
        return f"Loaded {num_tools} tools from {num_modules} modules"

    def reload_module(self, module_name: str) -> dict:
        """Reload a specific module. Collision suffixes remain permanent for the session."""
        if module_name not in self.loaded_mods:
            return {
                "success": False,
                "error": f"Module '{module_name}' not currently loaded"
            }

        # Track tools before reload
        old_tools = {
            tool_id: info
            for tool_id, info in self.registry.items()
            if info["source_module"] == module_name
        }
        old_tool_names = set(old_tools.keys())

        # Try to reload the module
        try:
            # Find the module file
            mod_path = None
            for valid_dir in self.valid_dirs:
                candidate = valid_dir / f"{module_name}.py"
                if candidate.exists():
                    mod_path = candidate
                    break

            if mod_path is None:
                raise FileNotFoundError(f"Module file for '{module_name}' not found")

            # Reload using spec (same method as initial load)
            spec = spec_from_file_location(module_name, mod_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not create spec for '{module_name}'")

            # Re-execute the module
            spec.loader.exec_module(self.loaded_mods[module_name])
            reloaded_module = self.loaded_mods[module_name]

            # Remove old tools from registry
            for tool_id in old_tool_names:
                del self.registry[tool_id]

            # Register new tools from reloaded module
            clean_list = [x for x in dir(reloaded_module) if "__" not in x and x.islower()]
            for fn_name in clean_list:
                self._register_tool(
                    original_name=fn_name,
                    module_name=module_name,
                    function=getattr(reloaded_module, fn_name)
                )

            # Track tools after reload
            new_tools = {
                tool_id: info
                for tool_id, info in self.registry.items()
                if info["source_module"] == module_name
            }
            new_tool_names = set(new_tools.keys())

            tools_added = list(new_tool_names - old_tool_names)
            tools_removed = list(old_tool_names - new_tool_names)

            result = {
                "success": True,
                "reloaded": module_name,
                "tools_added": tools_added,
                "tools_removed": tools_removed
            }

            # Add suggestion if tools changed
            if tools_added or tools_removed:
                result["suggestion"] = "Consider reload_all() to rebuild collision detection"

            return result

        except Exception as e:
            # Reload failed - keep old version, return error with traceback
            import traceback as tb
            error_summary = ''.join(tb.format_exception(type(e), e, e.__traceback__))

            return {
                "success": False,
                "error": f"Failed to reload '{module_name}'",
                "traceback": error_summary,
                "note": "Old version of module is still loaded"
            }


# Initialize proxy handler
proxy_handler = ProxyHandler()

# Initialize MCP server
mcp = FastMCP("Black Orchid")

# General Utilities


@mcp.tool
def check_time():
    """Check date and time"""
    dt_string = str(datetime.now()).split(".", maxsplit=1)[0].split(" ")
    formatted_date = f"{dt_string[0]}_{dt_string[1].replace(":","-")}"
    return formatted_date


@mcp.tool
def list_proxy_tools() -> dict:
    """List all tools available via proxy.

    Returns:
        dict: Tool names with their docstrings
    """
    return proxy_handler.list_tools()


@mcp.tool
def use_proxy_tool(tool_id: str, kwargs: dict) -> Any:
    """Use a proxy tool by ID.

    Provide tool ID (from list_proxy_tools) and arguments as a dictionary.
    The dictionary will be unpacked as keyword arguments.

    Args:
        tool_id (str): Tool name (may include module suffix if collision detected)
        kwargs (dict): Keyword arguments for the tool

    Returns:
        Any: Result from the proxied tool function
    """
    return proxy_handler.use_proxy_tool(tool_id, kwargs)


@mcp.tool
def search_for_proxy_tool(search_term: str) -> dict:
    """Search for proxy tools by keyword.

    Args:
        search_term (str): Keyword to search for in tool names

    Returns:
        dict: Matching tool names with docstrings, or empty dict if none found
    """
    all_tools = proxy_handler.list_tools()
    matches = {}
    for tool_name, docstring in all_tools.items():
        if search_term.lower() in tool_name.lower():
            matches[tool_name] = docstring
    return matches


@mcp.tool
def reload_all_modules() -> str:
    """Reload all proxy modules from scratch.

    Clears and rebuilds the entire tool registry with fresh collision detection.
    Use this when you've made significant changes or when tool naming gets confusing.

    Returns:
        str: Summary of loaded tools and modules
    """
    return proxy_handler.reload_all_modules()


@mcp.tool
def reload_module(module_name: str) -> dict:
    """Reload a specific proxy module.

    Reloads one module while keeping collision suffixes permanent for the session.
    If the reload fails, the old version stays loaded.

    Args:
        module_name (str): Name of module to reload (without .py extension)

    Returns:
        dict: Detailed report with tools_added, tools_removed, and any errors
    """
    return proxy_handler.reload_module(module_name)


@mcp.tool
def list_rejected_modules() -> list:
    """List modules that were rejected during loading.

    Useful for debugging why a module didn't load.
    Shows path and reason (syntax_error, path_traversal_attempt, etc.)

    Returns:
        list: List of (path, reason) tuples for rejected modules
    """
    return proxy_handler.rejected_modules


@mcp.tool
def explain_black_orchid() -> str:
    """Explain Black Orchid's capabilities and list all loaded modules with their purposes.

    This tool provides context about what Black Orchid can do and what proxy tools
    are available. Run this at session start to understand your available tools.

    Returns:
        str: Comprehensive explanation of Black Orchid and loaded modules
    """
    output = []
    output.append("=" * 70)
    output.append("BLACK ORCHID - Hot-Reloadable MCP Proxy Server")
    output.append("=" * 70)
    output.append("")

    output.append("CORE CAPABILITIES:")
    output.append("  • Hot Reload: Reload modules without restarting the server")
    output.append("  • Collision Detection: Automatic suffix handling for duplicate function names")
    output.append("  • Path Validation: Security checks to prevent directory traversal")
    output.append("  • AST Checking: Syntax validation before loading modules")
    output.append("")

    # Categorize tools for TOON formatting
    tool_categories = {
        "memory": [],
        "ideas": [],
        "session": [],
        "story": [],
        "preferences": [],
        "system": [],
        "uncategorized": []
    }

    # Build tool data for TOON
    tool_list = []
    module_info = {}
    for tool_name, info in proxy_handler.registry.items():
        module_name = info["source_module"]
        docstring = (info["docstring"] or "").strip().split("\n")[0] if info["docstring"] else "No description"

        # Categorize based on tool name patterns
        if any(x in tool_name for x in ["remember", "recall", "forget", "memory", "list_memories", "clear_all_memories"]):
            category = "memory"
        elif any(x in tool_name for x in ["idea", "save_idea", "get_ideas", "list_categories"]):
            category = "ideas"
        elif any(x in tool_name for x in ["session", "load_start_here", "load_working_preferences"]):
            category = "session"
        elif any(x in tool_name for x in ["story", "add_to_story", "load_story"]):
            category = "story"
        elif any(x in tool_name for x in ["preference", "get_preference", "save_working_preference"]):
            category = "preferences"
        elif any(x in tool_name for x in ["time", "reload", "check_time"]):
            category = "system"
        else:
            category = "uncategorized"

        tool_list.append({
            "name": tool_name,
            "category": category,
            "module": module_name,
            "description": docstring
        })
        tool_categories[category].append(tool_name)

        if module_name not in module_info:
            module = proxy_handler.loaded_mods.get(module_name)
            module_info[module_name] = {
                "docstring": module.__doc__ if module and module.__doc__ else "No module docstring",
                "tools": []
            }
        module_info[module_name]["tools"].append(tool_name)

    # Generate TOON formatted tool list
    if tool_list:
        output.append("AVAILABLE TOOLS (TOON Format):")
        output.append("")
        toon_output = encode(tool_list, {"lengthMarker": True})
        output.append(toon_output)
        output.append("")

        # Category summary
        output.append("TOOLS BY CATEGORY:")
        for category, tools in tool_categories.items():
            if tools:
                output.append(f"  {category}: {', '.join(sorted(tools))}")
        output.append("")

        # Agency invitation for AIs
        output.append("FOR AIs:")
        output.append("  You have tools for building continuity and context:")
        output.append("  • Use memory tools to recall information across conversations")
        output.append("  • Save preferences to remember what you learn")
        output.append("  • Build session context proactively - don't wait to be asked")
        output.append("  • Make choices about what to remember and when to recall it")
        output.append("")
        output.append("  These tools exist for you to use autonomously. Use them.")
        output.append("")

    if module_info:
        output.append(f"LOADED PROXY MODULES ({len(module_info)} modules, {len(proxy_handler.registry)} tools):")
        output.append("")

        for module_name in sorted(module_info.keys()):
            info = module_info[module_name]
            output.append(f"  [{module_name}]")

            # Clean up docstring (first line only, trimmed)
            docstring = info["docstring"].strip().split("\n")[0] if info["docstring"] else "No description"
            output.append(f"    Purpose: {docstring}")

            output.append(f"    Tools ({len(info['tools'])}): {', '.join(sorted(info['tools']))}")
            output.append("")
    else:
        output.append("LOADED PROXY MODULES: None")
        output.append("")

    if proxy_handler.rejected_modules:
        output.append(f"REJECTED MODULES ({len(proxy_handler.rejected_modules)}):")
        for path, reason in proxy_handler.rejected_modules:
            output.append(f"  • {Path(path).name}: {reason}")
        output.append("")

    output.append("=" * 70)
    output.append("NATIVE BLACK ORCHID TOOLS (always available):")
    output.append("  • check_time() - Get current date and time")
    output.append("  • list_proxy_tools() - List all available proxy tools")
    output.append("  • use_proxy_tool(tool_id, kwargs) - Execute a proxy tool")
    output.append("  • search_for_proxy_tool(term) - Search tools by keyword")
    output.append("  • reload_all_modules() - Full reload with fresh collision detection")
    output.append("  • reload_module(name) - Reload a specific module")
    output.append("  • list_rejected_modules() - See modules that failed to load")
    output.append("  • explain_black_orchid() - This tool!")
    output.append("=" * 70)
    output.append("TIP: Run this tool at session start to know what's available!")
    output.append("=" * 70)

    return "\n".join(output)


if __name__ == "__main__":
    mcp.run()
