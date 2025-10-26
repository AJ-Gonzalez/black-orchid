"""Fixture module - local documentation tools"""


def fetch_resource(path: str) -> str:
    """Fetch a resource from local filesystem (mock) - COLLISION with web_tools"""
    return f"Local content from {path}"


def index_documents(directory: str) -> list:
    """Index local documents (mock)"""
    return [f"doc1 in {directory}", "doc2", "doc3"]


def unique_docs_function() -> str:
    """A function unique to local_docs"""
    return "unique to docs"
