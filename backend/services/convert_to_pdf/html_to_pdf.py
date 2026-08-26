from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from backend.services.shared.renderers.html_renderer import render_html_to_pdf

def html_to_pdf(input_path: Path, output_path: Path) -> str:
    """Render HTML locally. WeasyPrint is preferred, ReportLab is the fallback."""
    try:
        from weasyprint import HTML, default_url_fetcher

        def local_only_fetcher(url: str, *args, **kwargs):
            scheme = urlparse(url).scheme.lower()
            if scheme in {"http", "https", "ftp"}:
                raise ValueError(
                    "Remote HTML assets are blocked. Embed assets as data URLs or keep them local."
                )
            return default_url_fetcher(url, *args, **kwargs)

        HTML(filename=str(input_path), base_url=str(input_path.parent), url_fetcher=local_only_fetcher).write_pdf(str(output_path))
        if output_path.exists() and output_path.stat().st_size:
            return "WeasyPrint"
    except Exception:
        # Windows systems can have a valid Python WeasyPrint package but miss
        # a native rendering DLL. Fall back instead of returning HTTP 500.
        pass
    return render_html_to_pdf(input_path, output_path)
