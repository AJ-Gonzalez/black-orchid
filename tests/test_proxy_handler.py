"""Tests for ProxyHandler collision detection and module loading

NOTE: These tests will be simplified once we create a proper test structure.
For now, they validate the core collision detection logic.
"""

import sys
import shutil
from pathlib import Path
import pytest

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
    for mod_name in ["web_tools", "local_docs", "broken_module"]:
        if mod_name in sys.modules:
            del sys.modules[mod_name]


def test_proxy_handler_loads_modules():
    """Test that ProxyHandler successfully loads valid modules"""
    handler = ProxyHandler()

    # Should have loaded web_tools and local_docs (broken_module should be skipped)
    assert "web_tools" in handler.loaded_mods
    assert "local_docs" in handler.loaded_mods
    assert "broken_module" not in handler.loaded_mods


def test_collision_detection_renames_both():
    """Test that colliding function names get suffixed"""
    handler = ProxyHandler()

    # fetch_resource exists in both web_tools and local_docs
    # Both should be renamed with module suffix
    assert "fetch_resource" not in handler.registry
    assert "fetch_resource_web_tools" in handler.registry
    assert "fetch_resource_local_docs" in handler.registry

    # Check collision flag
    assert handler.registry["fetch_resource_web_tools"]["had_collision"] is True
    assert handler.registry["fetch_resource_local_docs"]["had_collision"] is True


def test_unique_names_stay_simple():
    """Test that unique function names don't get suffixed"""
    handler = ProxyHandler()

    # These functions are unique to their modules
    assert "parse_html" in handler.registry
    assert "index_documents" in handler.registry
    assert "unique_web_function" in handler.registry
    assert "unique_docs_function" in handler.registry

    # They should NOT have collision flag
    assert handler.registry["parse_html"]["had_collision"] is False
    assert handler.registry["index_documents"]["had_collision"] is False


def test_use_proxy_tool_works():
    """Test that use_proxy_tool can invoke registered functions"""
    handler = ProxyHandler()

    # Test unique function
    result = handler.use_proxy_tool("parse_html", {"html": "<div>test</div>"})
    assert result["parsed"] is True
    assert result["content"] == "<div>test</div>"

    # Test collided function with suffix
    result = handler.use_proxy_tool("fetch_resource_web_tools", {"url": "http://example.com"})
    assert "Web content" in result

    result = handler.use_proxy_tool("fetch_resource_local_docs", {"path": "/docs/readme.md"})
    assert "Local content" in result


def test_use_proxy_tool_raises_on_invalid_id():
    """Test that use_proxy_tool raises KeyError for invalid tool_id"""
    handler = ProxyHandler()

    with pytest.raises(KeyError, match="Tool 'nonexistent' not found"):
        handler.use_proxy_tool("nonexistent", {})


def test_list_tools_returns_all_registered():
    """Test that list_tools returns all tools with docstrings"""
    handler = ProxyHandler()

    tools = handler.list_tools()

    # Should have all functions from both valid modules
    assert "fetch_resource_web_tools" in tools
    assert "fetch_resource_local_docs" in tools
    assert "parse_html" in tools
    assert "index_documents" in tools

    # Docstrings should be present
    assert "web" in tools["fetch_resource_web_tools"].lower()
    assert "local" in tools["fetch_resource_local_docs"].lower()


def test_broken_module_skipped():
    """Test that modules with syntax errors are skipped gracefully"""
    handler = ProxyHandler()

    # broken_module should not be in loaded modules
    assert "broken_module" not in handler.loaded_mods

    # And its functions should not be in registry
    assert "valid_function" not in handler.registry
    assert "broken_function" not in handler.registry
