"""
Librarian Service - Standalone Flask server for library document ingestion

Purpose: Handle long-running PDF ingestion tasks asynchronously via REST API
Usage: python librarian.py
Endpoints:
  GET  /status              - Service health and queue stats
  GET  /library             - List ingested documents
  POST /ingest              - Queue document for ingestion
  GET  /jobs/<job_id>       - Check job status
"""

from flask import Flask, request, jsonify
from pathlib import Path
import threading
import queue
import time
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

# Import from existing semantic_memory module
try:
    from modules.semantic_memory import (
        ingest_document,
        query_memory,
        initialize_semantic_memory
    )
except ImportError as e:
    print(f"ERROR: Failed to import semantic_memory: {e}")
    print("Make sure you're running from the black-orchid directory")
    exit(1)

# Configure logging to file only (not stdout - that breaks things)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('librarian.log', mode='a'),
    ]
)
logger = logging.getLogger('librarian')

# Flask app
app = Flask(__name__)

# Job queue and state
job_queue = queue.Queue()
jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = threading.Lock()

# Stats
stats = {
    'started': datetime.now().isoformat(),
    'jobs_completed': 0,
    'jobs_failed': 0,
    'total_documents_ingested': 0
}
stats_lock = threading.Lock()


def create_job(file_path: str, domain: str = 'library') -> str:
    """Create a new ingestion job and add to queue."""
    job_id = str(uuid.uuid4())[:8]  # Short ID for simplicity

    job = {
        'id': job_id,
        'file_path': file_path,
        'domain': domain,
        'status': 'pending',
        'created': datetime.now().isoformat(),
        'started': None,
        'completed': None,
        'error': None,
        'result': None
    }

    with jobs_lock:
        jobs[job_id] = job

    job_queue.put(job_id)
    logger.info(f"Created job {job_id} for {file_path}")

    return job_id


def update_job(job_id: str, updates: Dict[str, Any]):
    """Update job state thread-safely."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(updates)


def process_job(job_id: str):
    """Process a single ingestion job."""
    logger.info(f"Starting job {job_id}")

    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

    # Update to processing
    update_job(job_id, {
        'status': 'processing',
        'started': datetime.now().isoformat()
    })

    try:
        # Call existing ingest_document function
        result = ingest_document(
            file_path=job['file_path'],
            domain=job['domain']
        )

        if result.get('success'):
            # Success!
            update_job(job_id, {
                'status': 'completed',
                'completed': datetime.now().isoformat(),
                'result': result
            })

            with stats_lock:
                stats['jobs_completed'] += 1
                stats['total_documents_ingested'] += 1

            logger.info(f"Job {job_id} completed successfully: {result.get('nodes_added', 0)} nodes added")

        else:
            # Failed
            error = result.get('error', 'Unknown error')
            update_job(job_id, {
                'status': 'failed',
                'completed': datetime.now().isoformat(),
                'error': error
            })

            with stats_lock:
                stats['jobs_failed'] += 1

            logger.error(f"Job {job_id} failed: {error}")

    except Exception as e:
        # Unexpected error
        update_job(job_id, {
            'status': 'failed',
            'completed': datetime.now().isoformat(),
            'error': str(e)
        })

        with stats_lock:
            stats['jobs_failed'] += 1

        logger.error(f"Job {job_id} crashed: {e}", exc_info=True)


def worker_thread():
    """Background worker that processes job queue."""
    logger.info("Worker thread started")

    while True:
        try:
            # Get job from queue (blocks until available)
            job_id = job_queue.get(timeout=1)

            # Process it
            process_job(job_id)

            # Mark as done
            job_queue.task_done()

        except queue.Empty:
            # No jobs, keep waiting
            continue

        except Exception as e:
            logger.error(f"Worker thread error: {e}", exc_info=True)


# Start worker thread
worker = threading.Thread(target=worker_thread, daemon=True)
worker.start()


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/status', methods=['GET'])
def get_status():
    """Health check and queue stats."""
    with jobs_lock:
        pending = [j for j in jobs.values() if j['status'] == 'pending']
        processing = [j for j in jobs.values() if j['status'] == 'processing']
        completed = [j for j in jobs.values() if j['status'] == 'completed']
        failed = [j for j in jobs.values() if j['status'] == 'failed']

    with stats_lock:
        current_stats = dict(stats)

    return jsonify({
        'status': 'running',
        'uptime': (datetime.now() - datetime.fromisoformat(current_stats['started'])).total_seconds(),
        'queue': {
            'pending': len(pending),
            'processing': len(processing),
            'completed': len(completed),
            'failed': len(failed),
            'total_jobs': len(jobs)
        },
        'stats': current_stats
    })


@app.route('/library', methods=['GET'])
def get_library():
    """List ingested documents from ChromaDB."""
    try:
        # Query all documents from library domain
        # (This is a simple implementation - could be improved)
        result = query_memory(
            text="",  # Empty query to get all (if supported)
            domain='library',
            n_results=1000  # Large number to get everything
        )

        if result.get('success'):
            # Extract unique source files from results
            documents = set()
            for item in result.get('results', []):
                source_file = item.get('metadata', {}).get('source_file')
                if source_file:
                    documents.add(source_file)

            return jsonify({
                'success': True,
                'count': len(documents),
                'documents': sorted(list(documents))
            })

        else:
            return jsonify({
                'success': False,
                'error': 'Failed to query library'
            }), 500

    except Exception as e:
        logger.error(f"Error listing library: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/ingest', methods=['POST'])
def ingest():
    """Queue a document for ingestion."""
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'error': 'No JSON data provided'
        }), 400

    file_path = data.get('file_path')
    domain = data.get('domain', 'library')

    if not file_path:
        return jsonify({
            'success': False,
            'error': 'file_path is required'
        }), 400

    # Validate file exists
    if not Path(file_path).exists():
        return jsonify({
            'success': False,
            'error': f'File not found: {file_path}'
        }), 404

    # Create job
    job_id = create_job(file_path, domain)

    return jsonify({
        'success': True,
        'job_id': job_id,
        'message': f'Job {job_id} queued for processing',
        'check_status': f'/jobs/{job_id}'
    }), 202  # 202 Accepted


@app.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """Check job status."""
    with jobs_lock:
        job = jobs.get(job_id)

    if not job:
        return jsonify({
            'success': False,
            'error': f'Job {job_id} not found'
        }), 404

    # Return job info
    return jsonify({
        'success': True,
        'job': job
    })


@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List all jobs (optionally filtered by status)."""
    status_filter = request.args.get('status')

    with jobs_lock:
        if status_filter:
            filtered_jobs = [j for j in jobs.values() if j['status'] == status_filter]
        else:
            filtered_jobs = list(jobs.values())

    return jsonify({
        'success': True,
        'count': len(filtered_jobs),
        'jobs': filtered_jobs
    })


@app.route('/', methods=['GET'])
def index():
    """Root endpoint - simple info page."""
    return jsonify({
        'service': 'Librarian',
        'version': '1.0.0',
        'description': 'Document ingestion service for Black Orchid',
        'endpoints': {
            'GET /status': 'Service health and stats',
            'GET /library': 'List ingested documents',
            'POST /ingest': 'Queue document for ingestion',
            'GET /jobs/<id>': 'Check job status',
            'GET /jobs': 'List all jobs'
        },
        'version': '1.0.0'
    })


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("Librarian Service Starting")
    logger.info("=" * 80)

    # Initialize ChromaDB
    logger.info("Initializing semantic memory...")
    init_result = initialize_semantic_memory()

    if init_result.get('success'):
        logger.info(f"ChromaDB initialized: {init_result}")
    else:
        logger.error(f"Failed to initialize ChromaDB: {init_result}")
        print("ERROR: Failed to initialize ChromaDB")
        print("Check librarian.log for details")
        exit(1)

    # Start Flask
    logger.info("Starting Flask server on http://localhost:5000")
    print("Librarian Service starting...")
    print("Server: http://localhost:5000")
    print("Logs: librarian.log")
    print("Press Ctrl+C to stop")

    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=False,  # No debug in production
        threaded=True  # Handle multiple requests
    )
