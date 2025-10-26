"""System utilities for cross-platform OS and environment detection.

Provides tools to safely detect operating system, platform details,
and system specifications across Windows, Linux, macOS, and other platforms.
"""

import platform
import os


def _format_system_name(os_type):
    """Helper function to format OS names nicely.

    This function starts with underscore, so it won't be exposed as a tool.
    Used internally by get_os_info() for formatting.
    """
    if os_type == "Darwin":
        return "macOS"
    return os_type


def get_os_info():
    """Get comprehensive cross-platform operating system information.

    Returns detailed system information including OS type, version,
    architecture, Python version, and hostname. Works consistently
    across Windows, Linux, macOS, and other platforms.

    Returns:
        dict: System information with keys:
            - os_type: Operating system name (Windows, Linux, Darwin, etc.)
            - os_version: OS version/release information
            - os_release: OS release name
            - architecture: System architecture (x86_64, ARM64, etc.)
            - machine: Machine type
            - processor: Processor name (may be empty on some platforms)
            - python_version: Python version string
            - hostname: System hostname
            - platform: Complete platform string

    Example:
        >>> info = get_os_info()
        >>> print(f"Running on {info['os_type']} {info['os_version']}")
        Running on Windows 10
    """
    return {
        "os_type": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
        "platform": platform.platform(),
    }
