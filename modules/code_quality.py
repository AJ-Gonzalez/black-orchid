"""
Code Quality Audit Tools for Black Orchid Modules

Provides AST-based analysis of proxy modules to ensure compliance with
Black Orchid guidelines and coding standards.
"""

import ast
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import re


def audit_module(module_path: str) -> Dict[str, Any]:
    """
    Audit a Black Orchid module for code quality and guideline compliance.

    Checks for:
    - Missing docstrings on public functions
    - stdio usage (print, sys.stdout, etc.)
    - Missing type annotations
    - Inconsistent return patterns
    - Mis-scoped functions (helpers without _ prefix)
    - Module-level documentation

    Args:
        module_path: Path to module file (relative or absolute)

    Returns:
        dict: Audit results with violations categorized by severity

    Example:
        >>> audit_module('modules/semantic_memory.py')
        {
            'success': True,
            'module': 'semantic_memory.py',
            'critical': [...],
            'advisory': [...],
            'passed': [...],
            'exposed_tools': [...]
        }
    """
    path = Path(module_path)

    if not path.exists():
        return {
            'success': False,
            'error': f'Module not found: {module_path}'
        }

    # Read source code
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to read module: {e}'
        }

    # Parse AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            'success': False,
            'error': f'Syntax error at line {e.lineno}: {e.msg}'
        }

    # Run all checks
    critical_violations = []
    advisory_items = []
    passed_checks = []

    # Check 1: Module-level docstring
    module_doc = ast.get_docstring(tree)
    if not module_doc:
        advisory_items.append({
            'type': 'missing_module_docstring',
            'severity': 'advisory',
            'line': 1,
            'message': 'Module lacks docstring',
            'suggestion': 'Add module-level docstring explaining purpose and provided tools'
        })
    else:
        passed_checks.append('Module-level docstring present')

    # Check 2-7: Function-level checks
    docstring_issues = _check_docstrings(tree)
    type_hint_issues = _check_type_hints(tree)
    stdio_issues = _detect_stdio_usage(tree)
    return_pattern_issues = _check_return_patterns(tree)
    naming_issues = _check_function_naming(tree)

    critical_violations.extend(docstring_issues['critical'])
    advisory_items.extend(docstring_issues['advisory'])

    critical_violations.extend(stdio_issues)

    advisory_items.extend(type_hint_issues)
    advisory_items.extend(return_pattern_issues)
    advisory_items.extend(naming_issues)

    # Check stdio
    if not stdio_issues:
        passed_checks.append('No stdio usage detected')

    # Get list of exposed tools
    exposed_tools = _get_exposed_tools(tree)

    # Additional passed checks
    if not naming_issues:
        passed_checks.append('All function naming follows conventions')
    if not return_pattern_issues:
        passed_checks.append('Return value patterns consistent')

    return {
        'success': True,
        'module': path.name,
        'module_path': str(path),
        'critical': critical_violations,
        'advisory': advisory_items,
        'passed': passed_checks,
        'exposed_tools': exposed_tools,
        'summary': {
            'critical_count': len(critical_violations),
            'advisory_count': len(advisory_items),
            'passed_count': len(passed_checks),
            'exposed_tool_count': len(exposed_tools)
        }
    }


def generate_audit_report(audit_result: Dict[str, Any]) -> str:
    """
    Generate a markdown report from audit results.

    Args:
        audit_result: Results from audit_module()

    Returns:
        str: Formatted markdown report
    """
    if not audit_result.get('success'):
        return f"# Audit Failed\n\nError: {audit_result.get('error')}\n"

    module = audit_result['module']
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    critical = audit_result['critical']
    advisory = audit_result['advisory']
    passed = audit_result['passed']
    exposed = audit_result['exposed_tools']
    summary = audit_result['summary']

    # Build report
    lines = [
        f"# Code Quality Audit: {module}",
        f"**Generated:** {timestamp}",
        f"**Audit Scope:** Black Orchid proxy module guidelines compliance",
        "",
        "---",
        "",
        "## Summary",
        f"- ✅ **{summary['passed_count']} checks passed**",
        f"- ⚠️ **{summary['advisory_count']} advisory items**",
        f"- ❌ **{summary['critical_count']} critical violations**",
        f"- 📊 **Exposed as tools:** {summary['exposed_tool_count']} functions",
        "",
        "---",
        ""
    ]

    # Critical violations
    if critical:
        lines.append("## Critical Violations")
        lines.append("")
        for v in critical:
            lines.extend(_format_violation(v, "❌"))
        lines.append("---")
        lines.append("")
    else:
        lines.append("## Critical Violations")
        lines.append("")
        lines.append("✅ **No critical violations found!**")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Advisory items
    if advisory:
        lines.append("## Advisory Items")
        lines.append("")
        for v in advisory:
            lines.extend(_format_violation(v, "⚠️"))
        lines.append("---")
        lines.append("")

    # Passed checks
    if passed:
        lines.append("## Passed Checks")
        for check in passed:
            lines.append(f"✅ {check}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Exposed tools
    lines.append(f"## Exposed Tools ({len(exposed)} functions)")
    lines.append("")
    lines.append("These functions will be registered as MCP proxy tools:")
    lines.append("")

    for i, tool in enumerate(exposed, 1):
        status = "✅"
        # Check if this tool has violations
        for v in critical:
            if v.get('function') == tool['name']:
                status = "❌"
                break
        if status == "✅":
            for v in advisory:
                if v.get('function') == tool['name']:
                    status = "⚠️"
                    break

        lines.append(f"{i}. `{tool['name']}` {status}")

    return "\n".join(lines)


def save_audit_report(audit_result: Dict[str, Any], output_dir: str = "private/audit_reports") -> Dict[str, Any]:
    """
    Generate and save audit report to file.

    Args:
        audit_result: Results from audit_module()
        output_dir: Directory to save report (default: private/audit_reports)

    Returns:
        dict: Success status and file path
    """
    # Generate report
    report = generate_audit_report(audit_result)

    # Create output directory if needed
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
    module_name = audit_result.get('module', 'unknown').replace('.py', '')
    filename = f"{timestamp}_{module_name}.md"

    file_path = output_path / filename

    # Save report
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(report)

        return {
            'success': True,
            'file_path': str(file_path),
            'report': report
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to save report: {e}'
        }


# ============================================================================
# Helper Functions (not exposed as tools due to _ prefix)
# ============================================================================

def _check_docstrings(tree: ast.Module) -> Dict[str, List[Dict]]:
    """Check for missing or incomplete docstrings on public functions."""
    critical = []
    advisory = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Only check public functions (will be exposed as tools)
            if _is_public_function(node.name):
                docstring = ast.get_docstring(node)

                if not docstring:
                    critical.append({
                        'type': 'missing_docstring',
                        'severity': 'critical',
                        'function': node.name,
                        'line': node.lineno,
                        'message': f'Public function `{node.name}` will be exposed as tool without documentation',
                        'impact': 'Tool appears in MCP registry with empty description, unusable by LLM',
                        'fix': 'Add comprehensive docstring with Args and Returns sections'
                    })
                elif 'Args:' not in docstring or 'Returns:' not in docstring:
                    # Has docstring but incomplete
                    advisory.append({
                        'type': 'incomplete_docstring',
                        'severity': 'advisory',
                        'function': node.name,
                        'line': node.lineno,
                        'message': f'Docstring for `{node.name}` missing Args or Returns sections',
                        'suggestion': 'Add Args and Returns sections for complete documentation'
                    })

    return {'critical': critical, 'advisory': advisory}


def _check_type_hints(tree: ast.Module) -> List[Dict]:
    """Check for missing type annotations on public functions."""
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if _is_public_function(node.name):
                # Check parameters
                missing_params = []
                for arg in node.args.args:
                    if arg.annotation is None:
                        missing_params.append(arg.arg)

                # Check return type
                missing_return = node.returns is None

                if missing_params or missing_return:
                    issues.append({
                        'type': 'missing_type_hints',
                        'severity': 'advisory',
                        'function': node.name,
                        'line': node.lineno,
                        'message': f'Function `{node.name}` missing type annotations',
                        'details': {
                            'missing_params': missing_params,
                            'missing_return': missing_return
                        },
                        'suggestion': 'Add type hints for parameters and return value'
                    })

    return issues


def _detect_stdio_usage(tree: ast.Module) -> List[Dict]:
    """Detect print() calls and sys.stdout/stderr usage."""
    issues = []

    for node in ast.walk(tree):
        # Check for print() calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == 'print':
                issues.append({
                    'type': 'stdio_usage',
                    'severity': 'critical',
                    'line': node.lineno,
                    'message': 'Direct print() call detected',
                    'impact': 'stdio output will break MCP communication',
                    'fix': 'Remove print() or return data in function result instead'
                })

        # Check for sys.stdout/stderr usage
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id == 'sys' and node.attr in ['stdout', 'stderr']:
                    issues.append({
                        'type': 'stdio_usage',
                        'severity': 'critical',
                        'line': node.lineno,
                        'message': f'sys.{node.attr} usage detected',
                        'impact': 'stdio manipulation will break MCP communication',
                        'fix': 'Return data in function result instead of writing to stdio'
                    })

    return issues


def _check_return_patterns(tree: ast.Module) -> List[Dict]:
    """Check if functions follow {'success': bool} return convention."""
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if _is_public_function(node.name):
                # Look for return statements
                has_dict_return = False
                has_other_return = False

                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and child.value:
                        # Check if returning a dict
                        if isinstance(child.value, ast.Dict):
                            has_dict_return = True
                        else:
                            has_other_return = True

                # Advisory if not using dict returns
                if has_other_return and not has_dict_return:
                    issues.append({
                        'type': 'inconsistent_return_pattern',
                        'severity': 'advisory',
                        'function': node.name,
                        'line': node.lineno,
                        'message': f'Function `{node.name}` not using dict return pattern',
                        'suggestion': "Consider using {'success': bool, ...} return convention for consistency"
                    })

    return issues


def _check_function_naming(tree: ast.Module) -> List[Dict]:
    """Check for functions that might be mis-scoped (helpers without _ prefix)."""
    issues = []

    # Common helper function name patterns
    helper_patterns = [
        r'^format_',
        r'^parse_',
        r'^validate_',
        r'^build_',
        r'^create_',
        r'^process_',
    ]

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if _is_public_function(node.name):
                # Check if name suggests it might be a helper
                for pattern in helper_patterns:
                    if re.match(pattern, node.name):
                        # Check if it's used internally (called by other functions)
                        # This is a heuristic - if a function with helper-like name
                        # exists, it might be mis-scoped
                        issues.append({
                            'type': 'possibly_misscoped',
                            'severity': 'advisory',
                            'function': node.name,
                            'line': node.lineno,
                            'message': f'Function `{node.name}` has helper-like name but will be exposed as tool',
                            'suggestion': f'If this is internal helper, rename to `_{node.name}`. If it should be a tool, keep as-is.'
                        })
                        break

    return issues


def _get_exposed_tools(tree: ast.Module) -> List[Dict]:
    """Get list of functions that will be exposed as MCP tools."""
    tools = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if _is_public_function(node.name):
                tools.append({
                    'name': node.name,
                    'line': node.lineno,
                    'has_docstring': ast.get_docstring(node) is not None
                })

    return tools


def _is_public_function(name: str) -> bool:
    """Check if function name matches Black Orchid's tool exposure rules."""
    # Must be lowercase, no dunder, no underscore prefix
    return (
        name.islower() and
        '__' not in name and
        not name.startswith('_')
    )


def _format_violation(violation: Dict, icon: str) -> List[str]:
    """Format a violation for markdown output."""
    lines = [
        f"### {icon} {violation.get('message', 'Unknown issue')}",
        f"**Function:** `{violation.get('function', 'N/A')}` (Line {violation.get('line', '?')})",
        f"**Type:** {violation.get('type', 'unknown')}",
    ]

    if 'impact' in violation:
        lines.append(f"**Impact:** {violation['impact']}")

    if 'fix' in violation:
        lines.append(f"**Fix:** {violation['fix']}")

    if 'suggestion' in violation:
        lines.append(f"**Suggestion:** {violation['suggestion']}")

    if 'details' in violation:
        lines.append(f"**Details:** {violation['details']}")

    lines.append("")

    return lines
