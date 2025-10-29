"""Project utilities for file tree generation and documentation extraction"""
import ast
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import os

# Cache for project tree results
_project_tree_cache = {}
_cache_timestamp = 0
_cache_duration = 300  # 5 minutes

def _get_project_root(custom_root: Optional[str] = None) -> Path:
    """Get project root from custom path or current working directory

    Args:
        custom_root: Optional custom root path. If not provided, uses current working directory.

    Returns:
        Path object for the project root
    """
    if custom_root:
        return Path(custom_root).resolve()
    return Path(os.getcwd()).resolve()

def _extract_python_docstring(file_path: Path) -> Optional[str]:
    """Extract module-level docstring from Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Parse AST to get docstring
        tree = ast.parse(content)
        if (tree.body and isinstance(tree.body[0], ast.Expr) and
            isinstance(tree.body[0].value, (ast.Str, ast.Constant))):
            docstring = tree.body[0].value.s if hasattr(tree.body[0].value, 's') else tree.body[0].value.value
            if isinstance(docstring, str):
                # Return first line of docstring
                return docstring.split('\n')[0].strip()
    except Exception:
        pass
    return None

def _extract_js_description(file_path: Path) -> Optional[str]:
    """Extract description from JavaScript/TypeScript file comments"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Look for file-level comments at the top
        lines = content.split('\n')
        for i, line in enumerate(lines[:20]):  # Check first 20 lines
            line = line.strip()
            if line.startswith('//'):
                desc = line[2:].strip()
                if desc and not desc.startswith('@') and len(desc) > 10:
                    return desc
            elif line.startswith('/*'):
                # Multi-line comment
                comment_lines = []
                for j in range(i, min(i + 10, len(lines))):
                    comment_line = lines[j].strip()
                    if '*/' in comment_line:
                        break
                    if comment_line.startswith('*'):
                        comment_line = comment_line[1:].strip()
                    comment_lines.append(comment_line)
                if comment_lines:
                    desc = ' '.join(comment_lines).strip()
                    if len(desc) > 10:
                        return desc[:100] + '...' if len(desc) > 100 else desc
    except Exception:
        pass
    return None

def _extract_readme_description(file_path: Path) -> Optional[str]:
    """Extract description from README files"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Look for first paragraph or line after title
        lines = content.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('![') and len(line) > 20:
                return line[:100] + '...' if len(line) > 100 else line
    except Exception:
        pass
    return None

def _get_file_description(file_path: Path) -> Optional[str]:
    """Get description for a file based on its type"""
    suffix = file_path.suffix.lower()

    if suffix == '.py':
        return _extract_python_docstring(file_path)
    elif suffix in ['.js', '.ts', '.jsx', '.tsx']:
        return _extract_js_description(file_path)
    elif file_path.name.lower() in ['readme.md', 'readme.txt', 'readme']:
        return _extract_readme_description(file_path)
    elif suffix == '.json' and file_path.name == 'package.json':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('description', '')
        except Exception:
            pass

    return None

def _build_tree_structure(project_root: Path, include_stats: bool = False) -> Dict[str, Any]:
    """Build hierarchical tree structure with descriptions"""
    tree_data = {
        'name': project_root.name,
        'type': 'directory',
        'path': str(project_root),
        'children': []
    }

    def scan_directory(dir_path: Path, parent_node: Dict[str, Any], depth: int = 0) -> None:
        if depth > 10:  # Prevent infinite recursion
            return

        try:
            items = []
            for item in dir_path.iterdir():
                items.append(item)

            # Sort: directories first, then files alphabetically
            items.sort(key=lambda x: (x.is_file(), x.name.lower()))

            for item in items:
                node = {
                    'name': item.name,
                    'type': 'file' if item.is_file() else 'directory',
                    'path': str(item)
                }

                # Add file stats if requested
                if include_stats:
                    try:
                        stat = item.stat()
                        node['size'] = stat.st_size
                        node['modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                    except Exception:
                        pass

                # Get description for files
                if item.is_file():
                    description = _get_file_description(item)
                    if description:
                        node['description'] = description
                else:
                    node['children'] = []
                    scan_directory(item, node, depth + 1)

                parent_node['children'].append(node)

        except (PermissionError, Exception):
            pass

    scan_directory(project_root, tree_data)
    return tree_data

def _format_tree_output(tree_data: Dict[str, Any], indent: str = "") -> list[str]:
    """Format tree data into readable text output"""
    lines = []
    name = tree_data['name']
    description = tree_data.get('description', '')

    if tree_data['type'] == 'directory':
        lines.append(f"{indent}📁 {name}/")
    else:
        icon = "📄"
        if name.endswith('.py'):
            icon = "🐍"
        elif name.endswith(('.js', '.ts', '.jsx', '.tsx')):
            icon = "⚡"
        elif name.endswith('.json'):
            icon = "📋"
        elif name.lower().startswith('readme'):
            icon = "📖"

        desc_suffix = f" - {description}" if description else ""
        lines.append(f"{indent}{icon} {name}{desc_suffix}")

    # Add children for directories
    if 'children' in tree_data and tree_data['children']:
        child_indent = indent + "  "
        for child in tree_data['children']:
            lines.extend(_format_tree_output(child, child_indent))

    return lines

def full_project_tree(
    project_root: Optional[str] = None,
    include_stats: bool = False,
    filter_type: Optional[str] = None,
    max_depth: int = 10
) -> Dict[str, Any]:
    """Generate project file tree with extracted documentation and descriptions

    Args:
        project_root: Optional custom project root path. If not provided, uses current working directory.
        include_stats: Include file size and modification date
        filter_type: Filter by file type (e.g., 'py', 'js', 'md')
        max_depth: Maximum directory depth to scan

    Returns:
        Dict with tree structure and formatted output
    """
    try:
        # Check cache
        global _project_tree_cache, _cache_timestamp
        current_time = time.time()
        cache_key = f"{project_root}_{include_stats}_{filter_type}_{max_depth}"

        if (current_time - _cache_timestamp < _cache_duration and
            cache_key in _project_tree_cache):
            return _project_tree_cache[cache_key]

        # Get project root
        project_root_path = _get_project_root(project_root)
        if not project_root_path.exists():
            return {
                "error": f"Project root does not exist: {project_root_path}",
                "project_root": str(project_root_path)
            }

        start_time = time.time()

        # Build tree structure
        tree_data = _build_tree_structure(project_root_path, include_stats)

        # Apply filtering if requested
        if filter_type:
            def filter_tree(node: Dict[str, Any]) -> bool:
                if node['type'] == 'directory':
                    # Keep directories that have matching children
                    if 'children' in node:
                        node['children'] = [child for child in node['children'] if filter_tree(child)]
                        return len(node['children']) > 0
                    return True
                else:
                    # Keep files that match the filter
                    return node['name'].endswith(f'.{filter_type}')

            if 'children' in tree_data:
                tree_data['children'] = [child for child in tree_data['children'] if filter_tree(child)]

        # Format output
        formatted_lines = _format_tree_output(tree_data)

        processing_time = round(time.time() - start_time, 2)

        result = {
            "project_root": str(project_root_path),
            "tree_structure": tree_data,
            "formatted_output": "\n".join(formatted_lines),
            "processing_time_seconds": processing_time,
            "total_items": len(formatted_lines),
            "filters_applied": {
                "include_stats": include_stats,
                "filter_type": filter_type,
                "max_depth": max_depth
            }
        }

        # Update cache
        _project_tree_cache[cache_key] = result
        _cache_timestamp = current_time

        return result

    except Exception as e:
        return {
            "error": str(e),
            "project_root": str(_get_project_root(project_root)),
            "message": "Failed to generate project tree"
        }