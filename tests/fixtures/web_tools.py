"""Fixture module - web tools"""


def fetch_resource(url: str) -> str:
    """Fetch a resource from the web (mock)"""
    return f"Web content from {url}"


def parse_html(html: str) -> dict:
    """Parse HTML content (mock)"""
    return {"parsed": True, "content": html}


def unique_web_function() -> str:
    """A function unique to web_tools"""
    return "unique to web"
