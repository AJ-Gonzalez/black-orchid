"""Stateful Python REPL for interactive code execution.

Provides a persistent Python REPL environment that maintains state across
multiple tool calls. Perfect for iterative development, calculations,
data manipulation with pandas, and quick prototyping.

Features:
- Persistent sessions with maintained namespace
- Stdout/stderr capture
- Timeout protection
- Customizable standard library
- Session save/restore
- Token-efficient compared to file-based workflows
"""

import code
import sys
import io
import threading
import queue
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


# Module-level session storage (persists for server lifetime)
_repl_sessions: Dict[str, 'REPLSession'] = {}

# Standard library cache
_stdlib_code: Optional[str] = None
_stdlib_functions: Dict[str, Any] = {}


class REPLSession:
    """Represents a persistent Python REPL session."""

    def __init__(self, session_id: str, include_stdlib: bool = True):
        """Initialize a new REPL session.

        Args:
            session_id: Unique identifier for this session
            include_stdlib: Whether to load standard library
        """
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_executed = None
        self.execution_count = 0

        # Create namespace with standard library if requested
        self.namespace = {'__name__': '__console__', '__doc__': None}
        if include_stdlib:
            self.namespace.update(_load_stdlib())

        # Create interactive console
        self.console = code.InteractiveConsole(locals=self.namespace)

        # Execution history (optional, for debugging)
        self.history = []

    def execute(self, code_str: str, timeout: int = 55) -> Dict[str, Any]:
        """Execute code with output capture and timeout protection.

        Args:
            code_str: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            dict: Execution results with stdout, stderr, success status
        """
        result_queue = queue.Queue()
        exception_queue = queue.Queue()

        def worker():
            """Worker function to execute code with output capture."""
            try:
                # Save original streams
                old_stdout = sys.stdout
                old_stderr = sys.stderr

                # Create capture buffers
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()

                try:
                    # Redirect output streams
                    sys.stdout = stdout_capture
                    sys.stderr = stderr_capture

                    # Execute code line by line to handle multi-line statements
                    start_time = time.time()
                    more = False
                    for line in code_str.split('\n'):
                        more = self.console.push(line)

                    # If more is True, we have incomplete input (unfinished def, etc.)
                    # Push empty line to complete
                    if more:
                        self.console.push('')

                    execution_time = time.time() - start_time

                    # Get captured output
                    result_queue.put({
                        'stdout': stdout_capture.getvalue(),
                        'stderr': stderr_capture.getvalue(),
                        'execution_time': execution_time,
                        'needs_more_input': more
                    })

                finally:
                    # Always restore streams
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

            except Exception as e:
                exception_queue.put(e)

        # Run in thread with timeout
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        # Check if timeout occurred
        if thread.is_alive():
            return {
                'success': False,
                'error': f'Execution timeout ({timeout}s)',
                'note': 'Thread may still be running in background. Consider breaking infinite loops or reducing computation size.',
                'timeout': timeout
            }

        # Check for exceptions
        if not exception_queue.empty():
            exc = exception_queue.get()
            return {
                'success': False,
                'error': str(exc),
                'exception_type': type(exc).__name__
            }

        # Get successful result
        result = result_queue.get()
        result['success'] = True

        # Update session metadata
        self.last_executed = datetime.now()
        self.execution_count += 1
        self.history.append({
            'code': code_str,
            'timestamp': self.last_executed,
            'execution_time': result['execution_time']
        })

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics.

        Returns:
            dict: Session metadata and statistics
        """
        # Count user-defined variables (exclude builtins)
        user_vars = [k for k in self.namespace.keys()
                     if not k.startswith('_')]

        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'execution_count': self.execution_count,
            'variable_count': len(user_vars),
            'variables': user_vars
        }


def _load_stdlib() -> Dict[str, Any]:
    """Load standard library from private/repl_stdlib.py.

    Returns:
        dict: Namespace dictionary with stdlib imports and functions
    """
    global _stdlib_code, _stdlib_functions

    # Return cached if available
    if _stdlib_functions:
        return _stdlib_functions.copy()

    stdlib_file = Path('private/repl_stdlib.py')

    # If stdlib file doesn't exist, return empty dict
    if not stdlib_file.exists():
        return {}

    try:
        # Read stdlib code
        with open(stdlib_file, 'r', encoding='utf-8') as f:
            _stdlib_code = f.read()

        # Execute in temporary namespace to capture exports
        temp_namespace = {}
        exec(_stdlib_code, temp_namespace)

        # Cache for future use (exclude builtins)
        _stdlib_functions = {
            k: v for k, v in temp_namespace.items()
            if not k.startswith('_')
        }

        return _stdlib_functions.copy()

    except Exception as e:
        # If loading fails, return empty and log error
        print(f"Warning: Failed to load repl_stdlib.py: {e}")
        return {}


def _reload_stdlib():
    """Force reload of standard library from file.

    Used when stdlib is modified and needs to be reloaded.
    """
    global _stdlib_code, _stdlib_functions
    _stdlib_code = None
    _stdlib_functions = {}
    return _load_stdlib()


# ============================================================================
# TOOL FUNCTIONS (exposed to MCP)
# ============================================================================

def create_repl_session(session_id: Optional[str] = None,
                       include_stdlib: bool = True) -> Dict[str, Any]:
    """Create a new persistent Python REPL session.

    Creates a stateful Python REPL environment where variables, functions,
    and imports persist across multiple execute_repl() calls. Perfect for
    iterative development, data analysis, and quick prototyping.

    Args:
        session_id: Optional session identifier. If not provided, generates UUID.
        include_stdlib: Whether to auto-load standard library (default: True)

    Returns:
        dict: Session info with session_id and created timestamp

    Example:
        >>> create_repl_session("data_analysis")
        {'success': True, 'session_id': 'data_analysis', 'created_at': '...'}
    """
    # Generate ID if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())

    # Check if session already exists
    if session_id in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' already exists. Use destroy_repl_session() first or choose different ID."
        }

    # Create new session
    try:
        session = REPLSession(session_id, include_stdlib=include_stdlib)
        _repl_sessions[session_id] = session

        return {
            'success': True,
            'session_id': session_id,
            'created_at': session.created_at.isoformat(),
            'stdlib_loaded': include_stdlib
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to create session: {e}"
        }


def execute_repl(session_id: str, code: str, timeout: int = 55) -> Dict[str, Any]:
    """Execute Python code in a persistent REPL session.

    Runs the provided code in the specified session's namespace, capturing
    all output and maintaining state for future executions. Variables,
    functions, and imports persist across calls.

    Args:
        session_id: Target session identifier
        code: Python code to execute
        timeout: Maximum execution time in seconds (default: 55)

    Returns:
        dict: Execution results including:
            - success: Whether execution succeeded
            - stdout: Captured standard output
            - stderr: Captured standard error
            - execution_time: Time taken in seconds
            - needs_more_input: True if code is incomplete
            - error: Error message if failed

    Example:
        >>> execute_repl("calc", "import pandas as pd")
        {'success': True, 'stdout': '', 'stderr': '', ...}
        >>> execute_repl("calc", "df = pd.DataFrame({'a': [1,2,3]})")
        >>> execute_repl("calc", "print(df)")
        {'success': True, 'stdout': '   a\\n0  1\\n1  2\\n2  3\\n', ...}
    """
    # Check if session exists
    if session_id not in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' not found. Create it first with create_repl_session()."
        }

    # Get session and execute
    session = _repl_sessions[session_id]

    try:
        return session.execute(code, timeout=timeout)
    except Exception as e:
        return {
            'success': False,
            'error': f"Execution failed: {e}",
            'exception_type': type(e).__name__
        }


def list_repl_sessions() -> Dict[str, Any]:
    """List all active REPL sessions with their statistics.

    Returns:
        dict: List of sessions with their stats

    Example:
        >>> list_repl_sessions()
        {
            'count': 2,
            'sessions': [
                {'session_id': 'calc', 'execution_count': 5, ...},
                {'session_id': 'data', 'execution_count': 12, ...}
            ]
        }
    """
    sessions = [session.get_stats() for session in _repl_sessions.values()]

    return {
        'count': len(sessions),
        'sessions': sessions
    }


def get_session_namespace(session_id: str,
                         variable_name: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve variable value(s) from session namespace.

    Inspect variables defined in a REPL session. If variable_name is provided,
    returns that specific variable's value (as string representation). If not,
    returns list of all defined variable names.

    Args:
        session_id: Target session identifier
        variable_name: Specific variable to inspect (optional)

    Returns:
        dict: Variable info or list of variable names

    Example:
        >>> get_session_namespace("calc")
        {'variables': ['df', 'pd', 'result']}
        >>> get_session_namespace("calc", "result")
        {'variable': 'result', 'value': '42', 'type': 'int'}
    """
    # Check if session exists
    if session_id not in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' not found."
        }

    session = _repl_sessions[session_id]

    # If no variable specified, return all variable names
    if variable_name is None:
        user_vars = [k for k in session.namespace.keys()
                     if not k.startswith('_')]
        return {
            'success': True,
            'session_id': session_id,
            'variables': user_vars,
            'count': len(user_vars)
        }

    # Return specific variable
    if variable_name not in session.namespace:
        return {
            'success': False,
            'error': f"Variable '{variable_name}' not found in session."
        }

    value = session.namespace[variable_name]

    return {
        'success': True,
        'session_id': session_id,
        'variable': variable_name,
        'value': str(value),
        'type': type(value).__name__,
        'repr': repr(value)
    }


def destroy_repl_session(session_id: str) -> Dict[str, Any]:
    """Completely destroy a REPL session and free its resources.

    Args:
        session_id: Session to destroy

    Returns:
        dict: Success status

    Example:
        >>> destroy_repl_session("calc")
        {'success': True, 'message': 'Session destroyed'}
    """
    if session_id not in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' not found."
        }

    # Get stats before destroying
    stats = _repl_sessions[session_id].get_stats()

    # Remove session
    del _repl_sessions[session_id]

    return {
        'success': True,
        'message': f"Session '{session_id}' destroyed",
        'final_stats': stats
    }


def clear_repl_session(session_id: str) -> Dict[str, Any]:
    """Clear session namespace but keep session alive.

    Resets the namespace to initial state while preserving the session.
    Standard library will be reloaded if it was initially included.

    Args:
        session_id: Session to clear

    Returns:
        dict: Success status

    Example:
        >>> clear_repl_session("calc")
        {'success': True, 'message': 'Session cleared'}
    """
    if session_id not in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' not found."
        }

    session = _repl_sessions[session_id]

    # Reset namespace
    session.namespace.clear()
    session.namespace['__name__'] = '__console__'
    session.namespace['__doc__'] = None
    session.namespace.update(_load_stdlib())

    # Reset console with new namespace
    session.console = code.InteractiveConsole(locals=session.namespace)

    # Keep stats but clear history
    session.history.clear()

    return {
        'success': True,
        'message': f"Session '{session_id}' namespace cleared",
        'session_id': session_id
    }


def save_repl_session(session_id: str, filepath: str) -> Dict[str, Any]:
    """Save session namespace to file for later restoration.

    Serializes the session's namespace using pickle, allowing you to
    restore the session later with load_repl_session().

    Note: Only picklable objects will be saved. Some objects (like
    file handles, network connections) cannot be pickled.

    Args:
        session_id: Session to save
        filepath: Where to save the session (recommend .pkl extension)

    Returns:
        dict: Success status with file info

    Example:
        >>> save_repl_session("calc", "private/sessions/calc.pkl")
        {'success': True, 'filepath': 'private/sessions/calc.pkl', 'size_bytes': 1234}
    """
    import pickle

    if session_id not in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' not found."
        }

    session = _repl_sessions[session_id]
    filepath = Path(filepath)

    try:
        # Create parent directories if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Save namespace
        with open(filepath, 'wb') as f:
            pickle.dump(session.namespace, f)

        # Get file size
        size = filepath.stat().st_size

        return {
            'success': True,
            'message': f"Session saved to {filepath}",
            'filepath': str(filepath),
            'size_bytes': size,
            'session_id': session_id
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to save session: {e}"
        }


def load_repl_session(session_id: str, filepath: str) -> Dict[str, Any]:
    """Load session namespace from saved file.

    Restores a previously saved session, recreating all variables,
    functions, and imports from the saved namespace.

    Args:
        session_id: ID for the restored session (can be different from original)
        filepath: Path to saved session file (.pkl)

    Returns:
        dict: Success status with restored session info

    Example:
        >>> load_repl_session("calc_restored", "private/sessions/calc.pkl")
        {'success': True, 'session_id': 'calc_restored', 'variable_count': 15}
    """
    import pickle

    # Check if session ID already exists
    if session_id in _repl_sessions:
        return {
            'success': False,
            'error': f"Session '{session_id}' already exists. Destroy it first or use different ID."
        }

    filepath = Path(filepath)

    if not filepath.exists():
        return {
            'success': False,
            'error': f"File not found: {filepath}"
        }

    try:
        # Load namespace from file
        with open(filepath, 'rb') as f:
            namespace = pickle.load(f)

        # Create session with loaded namespace
        session = REPLSession.__new__(REPLSession)
        session.session_id = session_id
        session.created_at = datetime.now()
        session.last_executed = None
        session.execution_count = 0
        session.namespace = namespace
        session.console = code.InteractiveConsole(locals=session.namespace)
        session.history = []

        # Store session
        _repl_sessions[session_id] = session

        # Count variables
        user_vars = [k for k in namespace.keys() if not k.startswith('_')]

        return {
            'success': True,
            'message': f"Session loaded from {filepath}",
            'session_id': session_id,
            'variable_count': len(user_vars),
            'variables': user_vars
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to load session: {e}"
        }


def add_to_stdlib(function_code: str) -> Dict[str, Any]:
    """Add function to standard library for future sessions.

    Appends the provided function code to private/repl_stdlib.py,
    making it available in all future REPL sessions (when stdlib is enabled).
    Existing sessions are not affected.

    Args:
        function_code: Python function definition to add

    Returns:
        dict: Success status

    Example:
        >>> add_to_stdlib('''
        ... def quick_sort(arr):
        ...     if len(arr) <= 1:
        ...         return arr
        ...     pivot = arr[len(arr) // 2]
        ...     left = [x for x in arr if x < pivot]
        ...     middle = [x for x in arr if x == pivot]
        ...     right = [x for x in arr if x > pivot]
        ...     return quick_sort(left) + middle + quick_sort(right)
        ... ''')
        {'success': True, 'message': 'Function added to standard library'}
    """
    stdlib_file = Path('private/repl_stdlib.py')

    try:
        # Create file if it doesn't exist
        if not stdlib_file.exists():
            stdlib_file.parent.mkdir(parents=True, exist_ok=True)
            with open(stdlib_file, 'w', encoding='utf-8') as f:
                f.write('"""REPL Standard Library - Auto-loaded into new sessions."""\n\n')

        # Append function
        with open(stdlib_file, 'a', encoding='utf-8') as f:
            f.write('\n\n' + function_code + '\n')

        # Reload stdlib cache
        _reload_stdlib()

        return {
            'success': True,
            'message': f"Function added to {stdlib_file}",
            'note': 'New sessions will include this function. Existing sessions not affected.'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to add to stdlib: {e}"
        }


def list_stdlib_functions() -> Dict[str, Any]:
    """List all functions and objects in the standard library.

    Returns:
        dict: List of stdlib contents

    Example:
        >>> list_stdlib_functions()
        {
            'functions': ['quick_df', 'save_json', 'load_json'],
            'modules': ['pd', 'np', 'datetime'],
            'count': 6
        }
    """
    stdlib = _load_stdlib()

    # Categorize items
    functions = []
    modules = []
    other = []

    for name, obj in stdlib.items():
        if callable(obj):
            # Check if it's a function or callable class
            if hasattr(obj, '__module__'):
                if obj.__module__ != 'builtins':
                    functions.append(name)
            else:
                functions.append(name)
        elif hasattr(obj, '__name__'):
            # Likely a module
            modules.append(name)
        else:
            other.append(name)

    return {
        'success': True,
        'functions': functions,
        'modules': modules,
        'other': other,
        'count': len(stdlib)
    }
