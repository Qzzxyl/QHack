"""UI entry point, independent from the optimizer implementation."""
from pathlib import Path


def render_page(backend_enabled: bool = False) -> str:
    html = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    if backend_enabled:
        html = html.replace('name="universal-data-mode" content="demo"', 'name="universal-data-mode" content="backend"')
    return html
