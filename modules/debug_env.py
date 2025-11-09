"""Debug environment checker for MCP server."""

import sys
import importlib.util

def check_import_availability():
    """Check which optional libraries are available in this environment."""

    libraries = {
        'pymupdf4llm': False,
        'chromadb': False,
        'ebooklib': False,
        'mobi': False,
    }

    for lib in libraries:
        spec = importlib.util.find_spec(lib)
        libraries[lib] = spec is not None

    return {
        'python_version': sys.version,
        'python_path': sys.executable,
        'sys_path': sys.path,
        'libraries': libraries
    }
