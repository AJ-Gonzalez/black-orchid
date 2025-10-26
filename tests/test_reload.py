"""Tests for ProxyHandler reload functionality"""

import sys
import shutil
from pathlib import Path
import pytest
import time

# Add parent directory to path so we can import toolset
sys.path.insert(0, str(Path(__file__).parent.parent))

from toolset import ProxyHandler


@pytest.fixture(scope="session", autouse=True)
def setup_test_modules():
    """Copy test fixtures to modules directory for testing, cleanup after."""
    base_dir = Path(__file__).parent.parent
    modules_dir = base_dir / "modules"
    fixtures_dir = Path(__file__).parent / "fixtures"

    # Ensure modules directory exists
    modules_dir.mkdir(exist_ok=True)

    # Copy fixtures to modules
    copied_files = []
    for fixture_file in fixtures_dir.glob("*.py"):
        dest = modules_dir / fixture_file.name
        shutil.copy(fixture_file, dest)
        copied_files.append(dest)

    yield

    # Cleanup: remove copied test modules
    for file in copied_files:
        if file.exists():
            file.unlink()

    # Cleanup: remove from sys.modules
    for mod_name in ["web_tools", "local_docs", "broken_module", "test_module"]:
        if mod_name in sys.modules:
            del sys.modules[mod_name]


def test_reload_all_clears_and_rebuilds():
    """Test that reload_all() clears everything and rebuilds from scratch"""
    handler = ProxyHandler()

    initial_tool_count = len(handler.registry)
    initial_module_count = len(handler.loaded_mods)

    # Reload all
    result = handler.reload_all_modules()

    # Should have same counts (nothing changed on disk)
    assert len(handler.registry) == initial_tool_count
    assert len(handler.loaded_mods) == initial_module_count

    # Check result message format
    assert "Loaded" in result
    assert "tools from" in result
    assert "modules" in result


def test_reload_all_rebuilds_collision_detection():
    """Test that reload_all() rebuilds collision detection from scratch"""
    handler = ProxyHandler()

    # We know fetch_resource has collisions
    assert "fetch_resource_web_tools" in handler.registry
    assert "fetch_resource_local_docs" in handler.registry

    # Reload all
    handler.reload_all_modules()

    # Collision detection should be rebuilt - same suffixes should exist
    assert "fetch_resource_web_tools" in handler.registry
    assert "fetch_resource_local_docs" in handler.registry


def test_reload_module_adds_new_function():
    """Test that reload_module() detects when new functions are added"""
    base_dir = Path(__file__).parent.parent
    modules_dir = base_dir / "modules"
    test_module_path = modules_dir / "test_module.py"

    # Create a simple test module
    test_module_path.write_text('''"""Test module for reload testing"""

def original_function():
    """Original function"""
    return "original"
''')

    try:
        # Load initial - need to reload_all to pick up the new file
        handler = ProxyHandler()
        handler.reload_all_modules()  # Pick up test_module.py
        assert "original_function" in handler.registry
        assert "new_function" not in handler.registry

        # Modify the module to add a new function
        time.sleep(0.1)  # Ensure file timestamp changes
        test_module_path.write_text('''"""Test module for reload testing"""

def original_function():
    """Original function"""
    return "original"

def new_function():
    """Newly added function"""
    return "new"
''')

        # Reload the specific module
        result = handler.reload_module("test_module")

        # Check result
        assert result["success"] is True
        assert result["reloaded"] == "test_module"
        # Note: function names might have suffixes due to collision detection
        assert any("new_function" in tool for tool in result["tools_added"])
        assert "suggestion" in result  # Should suggest reload_all

        # Verify new function is now available (might have suffix)
        assert any("new_function" in tool for tool in handler.registry.keys())

    finally:
        # Cleanup
        if test_module_path.exists():
            test_module_path.unlink()
        if "test_module" in sys.modules:
            del sys.modules["test_module"]


def test_reload_module_removes_old_function():
    """Test that reload_module() detects when functions are removed

    NOTE: Due to permanent collision suffixes within a session, removed functions
    might still appear in the registry with suffixes. The suggestion to reload_all()
    handles this correctly.
    """
    base_dir = Path(__file__).parent.parent
    modules_dir = base_dir / "modules"
    test_module_path = modules_dir / "test_module.py"

    # Create a module with two functions
    test_module_path.write_text('''"""Test module for reload testing"""

def keep_this():
    """This function stays"""
    return "kept"

def remove_this():
    """This function will be removed"""
    return "removed"
''')

    try:
        # Load initial - need to reload_all to pick up the new file
        handler = ProxyHandler()
        handler.reload_all_modules()  # Pick up test_module.py

        # Get initial tool names (might have suffixes if collisions exist)
        initial_tools = [t for t in handler.registry.keys() if "keep_this" in t or "remove_this" in t]
        assert len(initial_tools) >= 2  # At least keep_this and remove_this in some form

        # Modify the module to remove a function
        time.sleep(0.1)
        test_module_path.write_text('''"""Test module for reload testing"""

def keep_this():
    """This function stays"""
    return "kept"
''')

        # Reload the specific module
        result = handler.reload_module("test_module")

        # Check result
        assert result["success"] is True
        # The tools_removed should show something was removed
        assert len(result["tools_removed"]) > 0
        # Should suggest reload_all since tool landscape changed
        assert "suggestion" in result

    finally:
        if test_module_path.exists():
            test_module_path.unlink()
        if "test_module" in sys.modules:
            del sys.modules["test_module"]


def test_reload_module_handles_syntax_error():
    """Test that reload_module() keeps old version when new version has syntax error"""
    base_dir = Path(__file__).parent.parent
    modules_dir = base_dir / "modules"
    test_module_path = modules_dir / "test_module.py"

    # Create a valid module
    test_module_path.write_text('''"""Test module for reload testing"""

def working_function():
    """This works"""
    return "working"
''')

    try:
        # Load initial - need to reload_all to pick up the new file
        handler = ProxyHandler()
        handler.reload_all_modules()  # Pick up test_module.py
        assert "working_function" in handler.registry

        # Test the function works
        result = handler.use_proxy_tool("working_function", {})
        assert result == "working"

        # Break the module with syntax error
        time.sleep(0.1)
        test_module_path.write_text('''"""Test module - BROKEN"""

def working_function()
    this is not valid python syntax
''')

        # Try to reload
        result = handler.reload_module("test_module")

        # Check error handling
        assert result["success"] is False
        assert "error" in result
        assert "traceback" in result
        assert "note" in result
        assert "Old version" in result["note"]

        # OLD VERSION SHOULD STILL WORK
        assert "working_function" in handler.registry
        old_result = handler.use_proxy_tool("working_function", {})
        assert old_result == "working"

    finally:
        if test_module_path.exists():
            test_module_path.unlink()
        if "test_module" in sys.modules:
            del sys.modules["test_module"]


def test_reload_module_collision_suffixes_stay_permanent():
    """Test that collision suffixes don't change during reload_module()"""
    handler = ProxyHandler()

    # web_tools loaded first, so fetch_resource got simple name initially
    # But collision was detected, so it became fetch_resource_web_tools
    assert "fetch_resource_web_tools" in handler.registry
    assert "fetch_resource_local_docs" in handler.registry

    # Reload web_tools
    result = handler.reload_module("web_tools")

    # Suffixes should stay the same (permanent for session)
    assert "fetch_resource_web_tools" in handler.registry
    assert result["success"] is True


def test_reload_nonexistent_module():
    """Test that reloading a non-loaded module returns error"""
    handler = ProxyHandler()

    result = handler.reload_module("nonexistent_module")

    assert result["success"] is False
    assert "not currently loaded" in result["error"]
