"""
Semantic Memory - Hierarchical Navigation System

Provides persistent, queryable memory with hierarchical structure and provenance tracking.
Uses ChromaDB for embedding storage and semantic search.

This module enables:
- Technical continuity (decisions, lessons, patterns)
- Personal memory (private notes, reflections, and confidential content)
- Reference library (books, papers, documentation)

Each domain maintains hierarchical structure with query cascading from general to specific.
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
from datetime import datetime

# Import config manager for domain configuration
try:
    from modules.config_manager import get_enabled_domains, is_domain_enabled
except ImportError:
    # Fallback if config_manager not available
    def get_enabled_domains():
        return ['technical', 'library']
    def is_domain_enabled(domain):
        return domain in get_enabled_domains()


# Database paths
DB_PATH = Path("./db/chroma")
SOURCES_PATH = Path("./sources")


def initialize_semantic_memory() -> Dict[str, Any]:
    """
    Initialize ChromaDB client and create memory collections.

    Creates persistent client and sets up collections for each memory domain.
    Safe to call multiple times - will reuse existing collections.

    Domains are loaded from config (public + private configs merged).

    Returns:
        dict: Status and available collections

    Example:
        >>> initialize_semantic_memory()
        {'success': True, 'collections': ['technical', 'library']}
    """
    try:
        # Create db directory if needed
        DB_PATH.mkdir(parents=True, exist_ok=True)

        # Initialize persistent client
        client = chromadb.PersistentClient(path=str(DB_PATH))

        # Get enabled domains from config
        domains = get_enabled_domains()
        collections = {}

        for domain in domains:
            collections[domain] = client.get_or_create_collection(
                name=f"memory_{domain}",
                metadata={"domain": domain, "version": "1.0"}
            )

        return {
            'success': True,
            'collections': domains,
            'db_path': str(DB_PATH),
            'note': 'Collections initialized or loaded successfully'
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to initialize semantic memory: {e}'
        }


def get_collections() -> Dict[str, Any]:
    """
    List available memory collections and their statistics.

    Returns:
        dict: Collection info including document counts

    Example:
        >>> get_collections()
        {'success': True, 'collections': {'technical': 42, 'library': 128}}
    """
    try:
        client = chromadb.PersistentClient(path=str(DB_PATH))

        collections_info = {}
        for collection in client.list_collections():
            coll_obj = client.get_collection(collection.name)
            collections_info[collection.name] = {
                'count': coll_obj.count(),
                'metadata': collection.metadata
            }

        return {
            'success': True,
            'collections': collections_info
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to get collections: {e}'
        }


def parse_markdown_hierarchy(file_path: str) -> Dict[str, Any]:
    """
    Parse markdown file into hierarchical structure based on headers.

    Extracts:
    - L0: Document (file itself)
    - L1: Major sections (# or ## headers)
    - L2: Subsections/paragraphs

    Args:
        file_path: Path to markdown file

    Returns:
        dict: Hierarchical structure with nodes at each level

    Example:
        >>> parse_markdown_hierarchy("sources/technical/decisions.md")
        {'success': True, 'hierarchy': {...}, 'levels': 2}
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {'success': False, 'error': f'File not found: {file_path}'}

        content = path.read_text(encoding='utf-8')

        # L0: Document level
        source_id = path.stem  # filename without extension

        hierarchy = {
            'source_id': source_id,
            'file_path': str(path),
            'L0': {
                'node_id': source_id,
                'title': source_id.replace('_', ' ').title(),
                'level': 0,
                'parent_id': None,
                'content': content[:500],  # First 500 chars as summary
                'path': source_id
            },
            'L1': [],
            'L2': []
        }

        # Split into sections by headers
        # Match # Header or ## Header
        header_pattern = re.compile(r'^(#{1,2})\s+(.+)$', re.MULTILINE)

        sections = []
        last_pos = 0
        current_section = None

        for match in header_pattern.finditer(content):
            # Save previous section's content
            if current_section:
                current_section['content'] = content[last_pos:match.start()].strip()
                sections.append(current_section)

            # Start new section
            level = len(match.group(1))  # Number of # symbols
            title = match.group(2).strip()

            current_section = {
                'level': 1 if level <= 2 else 2,  # Collapse to L1 or L2
                'title': title,
                'position': match.start()
            }
            last_pos = match.end()

        # Don't forget the last section
        if current_section:
            current_section['content'] = content[last_pos:].strip()
            sections.append(current_section)

        # Build L1 nodes
        for idx, section in enumerate([s for s in sections if s['level'] == 1]):
            node_id = f"{source_id}_L1_{idx}"
            hierarchy['L1'].append({
                'node_id': node_id,
                'title': section['title'],
                'level': 1,
                'parent_id': source_id,
                'content': section['content'][:1000],  # First 1000 chars
                'path': f"{source_id} > {section['title']}"
            })

        # Build L2 nodes (paragraphs within sections or all paragraphs if no L1)
        if hierarchy['L1']:
            # L2 from subsections
            for idx, section in enumerate([s for s in sections if s['level'] == 2]):
                node_id = f"{source_id}_L2_{idx}"
                # Find parent L1 by position
                parent_L1 = None
                for l1 in hierarchy['L1']:
                    if section['position'] > sections[[s for s in sections if s.get('title') == l1['title']][0] if any(s.get('title') == l1['title'] for s in sections) else None].get('position', 0):
                        parent_L1 = l1['node_id']

                hierarchy['L2'].append({
                    'node_id': node_id,
                    'title': section['title'],
                    'level': 2,
                    'parent_id': parent_L1 or source_id,
                    'content': section['content'],
                    'path': f"{source_id} > ... > {section['title']}"
                })
        else:
            # No headers - chunk into paragraphs as L2
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            for idx, para in enumerate(paragraphs[:20]):  # Limit to first 20 paragraphs
                node_id = f"{source_id}_L2_{idx}"
                hierarchy['L2'].append({
                    'node_id': node_id,
                    'title': para[:50] + '...',  # First 50 chars as title
                    'level': 2,
                    'parent_id': source_id,
                    'content': para,
                    'path': f"{source_id} > para_{idx}"
                })

        return {
            'success': True,
            'hierarchy': hierarchy,
            'levels': 2 if hierarchy['L2'] else (1 if hierarchy['L1'] else 0),
            'source_id': source_id
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to parse hierarchy: {e}'
        }


def ingest_document(file_path: str, domain: str = 'library') -> Dict[str, Any]:
    """
    Ingest a markdown document into semantic memory.

    Parses hierarchical structure and embeds each level in ChromaDB.

    Args:
        file_path: Path to markdown file
        domain: Memory domain (e.g., 'technical', 'library', 'custom')

    Returns:
        dict: Ingestion status and node counts

    Example:
        >>> ingest_document("sources/technical/decisions.md", domain="technical")
        {'success': True, 'nodes_added': 15, 'levels': 2}
    """
    try:
        # Validate domain against config
        valid_domains = get_enabled_domains()
        if domain not in valid_domains:
            return {
                'success': False,
                'error': f'Invalid domain. Must be one of: {valid_domains}'
            }

        # Parse hierarchy
        parse_result = parse_markdown_hierarchy(file_path)
        if not parse_result['success']:
            return parse_result

        hierarchy = parse_result['hierarchy']

        # Get collection
        client = chromadb.PersistentClient(path=str(DB_PATH))
        collection = client.get_or_create_collection(
            name=f"memory_{domain}",
            metadata={"domain": domain}
        )

        # Prepare documents for embedding
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
            'source_file': file_path
        })

        # Add L1
        for node in hierarchy['L1']:
            ids.append(node['node_id'])
            documents.append(node['content'])
            metadatas.append({
                'level': node['level'],
                'parent_id': node['parent_id'],
                'node_id': node['node_id'],
                'title': node['title'],
                'path': node['path'],
                'domain': domain,
                'source_file': file_path
            })

        # Add L2
        for node in hierarchy['L2']:
            ids.append(node['node_id'])
            documents.append(node['content'])
            metadatas.append({
                'level': node['level'],
                'parent_id': node['parent_id'],
                'node_id': node['node_id'],
                'title': node['title'],
                'path': node['path'],
                'domain': domain,
                'source_file': file_path
            })

        # Upsert to collection (adds or updates)
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        return {
            'success': True,
            'nodes_added': len(ids),
            'levels': parse_result['levels'],
            'source_id': hierarchy['source_id'],
            'domain': domain
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to ingest document: {e}'
        }


def query_memory(text: str, domain: str = 'technical', n_results: int = 5) -> Dict[str, Any]:
    """
    Query semantic memory with hierarchical cascading.

    Searches embeddings and returns results with full provenance.

    Args:
        text: Search query
        domain: Memory domain to search ('technical', 'library', or custom domain)
        n_results: Number of results to return

    Returns:
        dict: Search results with provenance chains

    Example:
        >>> query_memory("how did we solve REPL persistence?", domain="technical")
        {'success': True, 'results': [...], 'count': 3}
    """
    try:
        # Get collection
        client = chromadb.PersistentClient(path=str(DB_PATH))

        try:
            collection = client.get_collection(name=f"memory_{domain}")
        except Exception:
            return {
                'success': False,
                'error': f'Collection for domain "{domain}" not found. Try initializing first.'
            }

        # Query
        results = collection.query(
            query_texts=[text],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )

        # Format results
        formatted_results = []
        for idx in range(len(results['ids'][0])):
            formatted_results.append({
                'node_id': results['ids'][0][idx],
                'content': results['documents'][0][idx],
                'metadata': results['metadatas'][0][idx],
                'similarity_score': 1 - results['distances'][0][idx],  # Convert distance to similarity
                'path': results['metadatas'][0][idx].get('path', ''),
                'title': results['metadatas'][0][idx].get('title', ''),
                'level': results['metadatas'][0][idx].get('level', 0)
            })

        return {
            'success': True,
            'results': formatted_results,
            'count': len(formatted_results),
            'query': text,
            'domain': domain
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Query failed: {e}'
        }


def rebuild_domain(domain: str, source_paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Rebuild entire memory domain from sources directory or custom paths.

    Scans sources/{domain}/ for markdown files and re-ingests all, or uses
    provided source_paths list for custom locations.

    Args:
        domain: Domain to rebuild ('technical', 'library', 'personal', or custom domain)
        source_paths: Optional list of custom paths to scan instead of sources/{domain}/

    Returns:
        dict: Rebuild status with file counts

    Example:
        >>> rebuild_domain('technical')
        {'success': True, 'files_processed': 12, 'nodes_added': 157}
        >>> rebuild_domain('personal', source_paths=['private/notes'])
        {'success': True, 'files_processed': 20, 'nodes_added': 42}
    """
    try:
        # Determine source paths
        if source_paths:
            # Custom paths provided
            paths_to_scan = [Path(p) for p in source_paths]
        else:
            # Default to sources/{domain}/
            domain_path = SOURCES_PATH / domain
            if not domain_path.exists():
                return {
                    'success': False,
                    'error': f'Domain directory not found: {domain_path}'
                }
            paths_to_scan = [domain_path]

        # Clear existing collection
        client = chromadb.PersistentClient(path=str(DB_PATH))
        try:
            client.delete_collection(name=f"memory_{domain}")
        except Exception:
            pass  # Collection might not exist yet

        # Recreate collection
        client.get_or_create_collection(
            name=f"memory_{domain}",
            metadata={"domain": domain, "rebuilt_at": str(datetime.now())}
        )

        # Find all markdown files across all paths
        md_files = []
        for path in paths_to_scan:
            if path.is_file() and path.suffix == '.md':
                md_files.append(path)
            elif path.is_dir():
                md_files.extend(list(path.rglob("*.md")))

        if not md_files:
            return {
                'success': True,
                'files_processed': 0,
                'nodes_added': 0,
                'note': f'No markdown files found in specified paths'
            }

        # Ingest each file
        total_nodes = 0
        processed = 0
        errors = []

        for md_file in md_files:
            result = ingest_document(str(md_file), domain)
            if result['success']:
                total_nodes += result['nodes_added']
                processed += 1
            else:
                errors.append(f"{md_file.name}: {result['error']}")

        return {
            'success': True,
            'files_processed': processed,
            'nodes_added': total_nodes,
            'domain': domain,
            'errors': errors if errors else None
        }

    except Exception as e:
        return {
            'success': False,
            'error': f'Rebuild failed: {e}'
        }


def rebuild_personal_domain() -> Dict[str, Any]:
    """
    Rebuild personal memory domain from private/ directory.

    Scans and embeds private notes and confidential content from various
    private/ subdirectories including personal history, notes, and reference materials.

    Returns:
        dict: Rebuild status with file counts

    Example:
        >>> rebuild_personal_domain()
        {'success': True, 'files_processed': 30, 'nodes_added': 280, 'domain': 'personal'}
    """
    personal_paths = [
        'private/story',
        'private/notes',
        'private/reference'
    ]
    return rebuild_domain('personal', source_paths=personal_paths)


def rebuild_technical_domain() -> Dict[str, Any]:
    """
    Rebuild technical memory domain from private/design_docs/.

    Scans and embeds all design documents and technical notes.

    Returns:
        dict: Rebuild status with file counts

    Example:
        >>> rebuild_technical_domain()
        {'success': True, 'files_processed': 8, 'nodes_added': 124, 'domain': 'technical'}
    """
    return rebuild_domain('technical', source_paths=['private/design_docs'])
