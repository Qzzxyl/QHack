"""Regenerate the shareable standalone page after editing static/ files."""
from base64 import b64encode
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    static = ROOT / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    css = (static / "styles.css").read_text(encoding="utf-8-sig")
    js = (static / "app.js").read_text(encoding="utf-8")
    for photo in sorted(static.glob("ride-*.*")):
        subtype = "jpeg" if photo.suffix == ".jpg" else "png"
        encoded = b64encode(photo.read_bytes()).decode("ascii")
        js = js.replace(f"'/{photo.name}'", f"'data:image/{subtype};base64,{encoded}'")
    html = html.replace(
        '<link rel="stylesheet" href="/styles.css"><script src="/app.js" defer></script>',
        "<style>" + css + "</style>",
    )
    html = html.replace('<a class="brand" href="/"', '<a class="brand" href="#"')
    html = html.replace("</body>", "<script>" + js + "</script></body>")
    globe = b64encode((static / "universal-globe.png").read_bytes()).decode("ascii")
    html = html.replace('src="/universal-globe.png"', f'src="data:image/png;base64,{globe}"')
    target = ROOT / "Universal-Day-English.html"
    target.write_text(html, encoding="utf-8")
    print(f"Created: {target}")


if __name__ == "__main__":
    build()
