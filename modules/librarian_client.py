"""
Librarian Client - Black Orchid proxy tools for document ingestion service

Provides tools to interact with the Librarian Flask service via HTTP.
The librarian handles long-running PDF ingestion tasks asynchronously.
"""

import requests
from pathlib import Path
from typing import Dict, Any, Optional, List
import time


LIBRARIAN_URL = "http://localhost:5000"


def librarian_status() -> Dict[str, Any]:
    """
    Check librarian service health and queue statistics.

    Returns:
        dict: Service status including uptime, queue stats, and job counts

    Example:
        >>> librarian_status()
        {
            'success': True,
            'status': 'running',
            'uptime': 123.45,
            'queue': {'pending': 2, 'processing': 1, 'completed': 5, 'failed': 0},
            'stats': {...}
        }
    """
    try:
        response = requests.get(f"{LIBRARIAN_URL}/status", timeout=5)

        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                **data
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }

    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Librarian service is not running. Start it with: python librarian.py'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to check status: {str(e)}'
        }


def librarian_ingest(file_path: str, domain: str = 'library') -> Dict[str, Any]:
    """
    Queue a document for ingestion into semantic memory.

    Args:
        file_path: Path to document (relative or absolute)
        domain: Memory domain (default: 'library')

    Returns:
        dict: Job information including job_id for status checking

    Example:
        >>> librarian_ingest('sources/library/golang-for-python-programmers.pdf')
        {
            'success': True,
            'job_id': 'a1b2c3d4',
            'message': 'Job a1b2c3d4 queued for processing',
            'check_status': '/jobs/a1b2c3d4'
        }
    """
    # Validate file exists
    path = Path(file_path)
    if not path.exists():
        return {
            'success': False,
            'error': f'File not found: {file_path}'
        }

    # Convert to absolute path for librarian
    abs_path = str(path.resolve())

    try:
        response = requests.post(
            f"{LIBRARIAN_URL}/ingest",
            json={
                'file_path': abs_path,
                'domain': domain
            },
            timeout=10
        )

        if response.status_code == 202:  # Accepted
            data = response.json()
            return {
                'success': True,
                **data
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.json().get("error", response.text)}'
            }

    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Librarian service is not running. Start it with: python librarian.py'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to queue ingestion: {str(e)}'
        }


def librarian_check_job(job_id: str) -> Dict[str, Any]:
    """
    Check the status of an ingestion job.

    Args:
        job_id: Job ID returned from librarian_ingest

    Returns:
        dict: Job details including status (pending/processing/completed/failed)

    Example:
        >>> librarian_check_job('a1b2c3d4')
        {
            'success': True,
            'job': {
                'id': 'a1b2c3d4',
                'file_path': '...',
                'status': 'completed',
                'created': '2025-11-09T...',
                'completed': '2025-11-09T...',
                'result': {'nodes_added': 42, ...}
            }
        }
    """
    try:
        response = requests.get(f"{LIBRARIAN_URL}/jobs/{job_id}", timeout=5)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {
                'success': False,
                'error': f'Job {job_id} not found'
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }

    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Librarian service is not running'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to check job: {str(e)}'
        }


def librarian_list_jobs(status_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    List all ingestion jobs, optionally filtered by status.

    Args:
        status_filter: Optional status to filter by (pending/processing/completed/failed)

    Returns:
        dict: List of jobs matching the filter

    Example:
        >>> librarian_list_jobs('completed')
        {
            'success': True,
            'count': 5,
            'jobs': [...]
        }
    """
    try:
        params = {'status': status_filter} if status_filter else {}
        response = requests.get(f"{LIBRARIAN_URL}/jobs", params=params, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }

    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Librarian service is not running'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to list jobs: {str(e)}'
        }


def librarian_list_library() -> Dict[str, Any]:
    """
    List all documents currently in the library (semantic memory).

    Returns:
        dict: List of ingested document paths

    Example:
        >>> librarian_list_library()
        {
            'success': True,
            'count': 12,
            'documents': ['sources/library/book1.pdf', ...]
        }
    """
    try:
        response = requests.get(f"{LIBRARIAN_URL}/library", timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text}'
            }

    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Librarian service is not running'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to list library: {str(e)}'
        }


def librarian_ingest_directory(directory: str, domain: str = 'library',
                               pattern: str = '*.pdf') -> Dict[str, Any]:
    """
    Queue all matching files in a directory for ingestion.

    Args:
        directory: Directory path to scan
        domain: Memory domain (default: 'library')
        pattern: Glob pattern for files (default: '*.pdf')

    Returns:
        dict: Summary of queued jobs

    Example:
        >>> librarian_ingest_directory('sources/library')
        {
            'success': True,
            'queued': 12,
            'job_ids': ['a1b2c3d4', ...],
            'skipped': 0,
            'errors': []
        }
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        return {
            'success': False,
            'error': f'Directory not found: {directory}'
        }

    if not dir_path.is_dir():
        return {
            'success': False,
            'error': f'Not a directory: {directory}'
        }

    # Find all matching files
    files = list(dir_path.glob(pattern))

    if not files:
        return {
            'success': True,
            'queued': 0,
            'job_ids': [],
            'skipped': 0,
            'errors': [],
            'message': f'No files matching {pattern} found in {directory}'
        }

    # Queue each file
    job_ids = []
    errors = []

    for file_path in files:
        result = librarian_ingest(str(file_path), domain)

        if result.get('success'):
            job_ids.append(result['job_id'])
        else:
            errors.append({
                'file': str(file_path),
                'error': result.get('error')
            })

    return {
        'success': True,
        'queued': len(job_ids),
        'job_ids': job_ids,
        'skipped': 0,
        'errors': errors,
        'total_files': len(files)
    }


def librarian_wait_for_job(job_id: str, timeout: int = 600,
                           poll_interval: int = 5) -> Dict[str, Any]:
    """
    Wait for a job to complete (blocking).

    Args:
        job_id: Job ID to wait for
        timeout: Maximum seconds to wait (default: 600 = 10 minutes)
        poll_interval: Seconds between status checks (default: 5)

    Returns:
        dict: Final job status

    Example:
        >>> result = librarian_wait_for_job('a1b2c3d4')
        # Blocks until job completes or times out
    """
    start_time = time.time()

    while True:
        # Check if timeout exceeded
        if time.time() - start_time > timeout:
            return {
                'success': False,
                'error': f'Timeout waiting for job {job_id} after {timeout} seconds',
                'job_id': job_id
            }

        # Check job status
        result = librarian_check_job(job_id)

        if not result.get('success'):
            return result  # Error checking status

        job = result.get('job', {})
        status = job.get('status')

        # Job completed (success or failure)
        if status in ['completed', 'failed']:
            return result

        # Still pending/processing, wait and try again
        time.sleep(poll_interval)
