"""
Standalone PDF/Document Ingestion Diagnostic Script

Purpose: Diagnose performance bottlenecks in document ingestion pipeline
Usage:
  python test_pdf_ingestion.py              # Test files (sources/library/test/)
  python test_pdf_ingestion.py -b           # Full library (sources/library/)
Output: Logs to pdf_ingestion_diagnostic.log

Tests document ingestion with full timing and diagnostics.
"""

import time
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List
import chromadb
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_ingestion_diagnostic.log', mode='w'),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)

# Import from existing modules
try:
    from modules.semantic_memory import (
        detect_document_format,
        parse_markdown_hierarchy,
        parse_pdf_document,
        DB_PATH
    )
    logger.info("[OK] Successfully imported semantic_memory functions")
except ImportError as e:
    logger.error(f"[FAIL] Failed to import semantic_memory: {e}")
    exit(1)


def format_time(seconds: float) -> str:
    """Format seconds into readable time string."""
    if seconds < 1:
        return f"{seconds*1000:.2f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.2f}s"


def get_file_size_str(path: Path) -> str:
    """Get human-readable file size."""
    size = path.stat().st_size
    if size < 1024:
        return f"{size}B"
    elif size < 1024**2:
        return f"{size/1024:.2f}KB"
    elif size < 1024**3:
        return f"{size/(1024**2):.2f}MB"
    else:
        return f"{size/(1024**3):.2f}GB"


def ingest_single_document(file_path: Path, domain: str = 'library') -> Dict[str, Any]:
    """
    Ingest a single document with full timing and diagnostics.

    Returns dict with timing breakdown and results.
    """
    logger.info("=" * 80)
    logger.info(f"INGESTING: {file_path.name}")
    logger.info("=" * 80)

    results = {
        'file_path': str(file_path),
        'file_name': file_path.name,
        'file_size': get_file_size_str(file_path),
        'file_size_bytes': file_path.stat().st_size,
        'success': False,
        'timings': {},
        'nodes': {},
        'errors': []
    }

    total_start = time.time()

    try:
        # Step 1: Detect format
        logger.info(f"File size: {results['file_size']}")
        format_start = time.time()
        doc_format = detect_document_format(str(file_path))
        results['format'] = doc_format
        results['timings']['format_detection'] = time.time() - format_start
        logger.info(f"[OK] Format detected: {doc_format} ({format_time(results['timings']['format_detection'])})")

        # Step 2: Parse document
        parse_start = time.time()
        logger.info(f"Starting {doc_format} parsing...")

        if doc_format == 'pdf':
            parse_result = parse_pdf_document(str(file_path))
        elif doc_format == 'markdown':
            parse_result = parse_markdown_hierarchy(str(file_path))
        else:
            raise ValueError(f"Unsupported format: {doc_format}")

        results['timings']['parsing'] = time.time() - parse_start
        logger.info(f"[OK] Parsing complete: {format_time(results['timings']['parsing'])}")

        if not parse_result['success']:
            results['errors'].append(f"Parsing failed: {parse_result.get('error', 'Unknown error')}")
            logger.error(f"[FAIL] Parsing failed: {parse_result.get('error')}")
            return results

        hierarchy = parse_result['hierarchy']

        # Log hierarchy stats
        logger.info(f"Hierarchy extracted:")
        for level in ['L0', 'L1', 'L2', 'L3']:
            if level in hierarchy:
                if level == 'L0':
                    count = 1
                    results['nodes'][level] = 1
                else:
                    count = len(hierarchy[level])
                    results['nodes'][level] = count
                logger.info(f"  {level}: {count} nodes")

        # Step 3: Initialize ChromaDB
        db_start = time.time()
        logger.info("Initializing ChromaDB client...")
        client = chromadb.PersistentClient(path=str(DB_PATH))
        collection = client.get_or_create_collection(
            name=f"memory_{domain}",
            metadata={"domain": domain}
        )
        results['timings']['chromadb_init'] = time.time() - db_start
        logger.info(f"[OK] ChromaDB initialized: {format_time(results['timings']['chromadb_init'])}")
        logger.info(f"  Collection: memory_{domain}")
        logger.info(f"  DB Path: {DB_PATH}")

        # Step 4: Prepare batches
        prep_start = time.time()
        logger.info("Preparing nodes for embedding...")

        ids = []
        documents = []
        metadatas = []

        # Add L0
        l0 = hierarchy['L0']
        ids.append(l0['node_id'])
        documents.append(l0['content'])
        metadatas.append({
            'level': l0['level'],
            'parent_id': '',
            'node_id': l0['node_id'],
            'title': l0['title'],
            'path': l0['path'],
            'domain': domain,
            'source_file': str(file_path),
            'format': hierarchy.get('format', doc_format)
        })

        # Add L1
        for node in hierarchy.get('L1', []):
            ids.append(node['node_id'])
            documents.append(node['content'])
            metadatas.append({
                'level': node['level'],
                'parent_id': node['parent_id'],
                'node_id': node['node_id'],
                'title': node['title'],
                'path': node['path'],
                'domain': domain,
                'source_file': str(file_path),
                'format': hierarchy.get('format', doc_format)
            })

        # Add L2
        for node in hierarchy.get('L2', []):
            ids.append(node['node_id'])
            documents.append(node['content'])
            metadatas.append({
                'level': node['level'],
                'parent_id': node['parent_id'],
                'node_id': node['node_id'],
                'title': node['title'],
                'path': node['path'],
                'domain': domain,
                'source_file': str(file_path),
                'format': hierarchy.get('format', doc_format)
            })

        # Add L3
        for node in hierarchy.get('L3', []):
            ids.append(node['node_id'])
            documents.append(node['content'])
            metadatas.append({
                'level': node['level'],
                'parent_id': node['parent_id'],
                'node_id': node['node_id'],
                'title': node['title'],
                'path': node['path'],
                'domain': domain,
                'source_file': str(file_path),
                'format': hierarchy.get('format', doc_format)
            })

        results['timings']['node_preparation'] = time.time() - prep_start
        results['total_nodes'] = len(ids)
        logger.info(f"[OK] Nodes prepared: {len(ids)} total ({format_time(results['timings']['node_preparation'])})")

        # Log content size stats
        total_chars = sum(len(doc) for doc in documents)
        avg_chars = total_chars / len(documents) if documents else 0
        logger.info(f"  Total content: {total_chars:,} chars")
        logger.info(f"  Avg per node: {avg_chars:.0f} chars")

        # Step 5: Upsert to ChromaDB (embeddings generated here)
        embed_start = time.time()
        logger.info("Upserting to ChromaDB (generating embeddings)...")
        logger.info("  [WARNING] This step may take a while for large documents...")

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        results['timings']['embedding_and_storage'] = time.time() - embed_start
        logger.info(f"[OK] Embeddings generated and stored: {format_time(results['timings']['embedding_and_storage'])}")

        # Get collection stats
        collection_count = collection.count()
        logger.info(f"  Collection now contains: {collection_count} total nodes")

        results['success'] = True

    except Exception as e:
        logger.error(f"[ERROR] ERROR during ingestion: {e}", exc_info=True)
        results['errors'].append(str(e))

    finally:
        results['timings']['total'] = time.time() - total_start

        # Log summary
        logger.info("-" * 80)
        logger.info("TIMING SUMMARY:")
        for step, duration in results['timings'].items():
            logger.info(f"  {step:30s}: {format_time(duration)}")
        logger.info("-" * 80)

        if results['success']:
            logger.info(f"[SUCCESS] {file_path.name} ingested in {format_time(results['timings']['total'])}")
        else:
            logger.error(f"[FAILED] {file_path.name}")
            for error in results['errors']:
                logger.error(f"  - {error}")
        logger.info("")

    return results


def main():
    """Main diagnostic routine."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Diagnose document ingestion performance with timing details'
    )
    parser.add_argument(
        '-b', '--books',
        action='store_true',
        help='Process full library (sources/library/) instead of test files'
    )
    args = parser.parse_args()

    # Determine which directory to process
    if args.books:
        test_dir = Path("sources/library")
        mode_label = "FULL LIBRARY"
    else:
        test_dir = Path("sources/library/test")
        mode_label = "TEST FILES"

    logger.info("=" * 80)
    logger.info(" PDF/Document Ingestion Diagnostic Script ".center(80))
    logger.info(f" Mode: {mode_label} ".center(80))
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Source directory: {test_dir}")
    logger.info(f"Database path: {DB_PATH}")
    logger.info("")

    if not test_dir.exists():
        logger.error(f"[FAIL] Source directory not found: {test_dir}")
        logger.info(f"Please ensure {test_dir} exists and contains files")
        return

    # Get all files (not directories)
    test_files = [f for f in test_dir.iterdir() if f.is_file()]

    if not test_files:
        logger.warning(f"[WARNING] No files found in {test_dir}")
        return

    logger.info(f"Found {len(test_files)} files to process:")
    for f in test_files:
        logger.info(f"  - {f.name} ({get_file_size_str(f)})")
    logger.info("")

    # Process each file
    all_results = []
    for test_file in test_files:
        result = ingest_single_document(test_file, domain='library')
        all_results.append(result)

    # Final summary
    logger.info("")
    logger.info("=" * 80)
    logger.info(" FINAL SUMMARY ".center(80))
    logger.info("=" * 80)
    logger.info("")

    successful = [r for r in all_results if r['success']]
    failed = [r for r in all_results if not r['success']]

    logger.info(f"Total files processed: {len(all_results)}")
    logger.info(f"  [OK] Successful: {len(successful)}")
    logger.info(f"  [FAIL] Failed: {len(failed)}")
    logger.info("")

    if successful:
        logger.info("Performance breakdown (successful files):")
        logger.info("")
        logger.info(f"{'File':<40} {'Format':<10} {'Nodes':<8} {'Total Time':<15}")
        logger.info("-" * 80)
        for r in successful:
            logger.info(
                f"{r['file_name']:<40} "
                f"{r['format']:<10} "
                f"{r['total_nodes']:<8} "
                f"{format_time(r['timings']['total']):<15}"
            )
        logger.info("")

        # Timing averages
        avg_parse = sum(r['timings']['parsing'] for r in successful) / len(successful)
        avg_embed = sum(r['timings']['embedding_and_storage'] for r in successful) / len(successful)
        avg_total = sum(r['timings']['total'] for r in successful) / len(successful)

        logger.info("Average timings:")
        logger.info(f"  Parsing:              {format_time(avg_parse)}")
        logger.info(f"  Embedding & Storage:  {format_time(avg_embed)}")
        logger.info(f"  Total:                {format_time(avg_total)}")

    if failed:
        logger.info("")
        logger.info("Failed files:")
        for r in failed:
            logger.info(f"  [FAIL] {r['file_name']}")
            for error in r['errors']:
                logger.info(f"    - {error}")

    logger.info("")
    logger.info(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Full log saved to: pdf_ingestion_diagnostic.log")


if __name__ == "__main__":
    main()
