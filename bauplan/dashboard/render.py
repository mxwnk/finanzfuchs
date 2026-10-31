"""Puts the dataset and ECharts into the dashboard page: one self-contained HTML file.

Nothing is loaded from the internet, so the page works offline and leaks no request about the
family's finances to a CDN.
"""

import json
from importlib import resources
from typing import Any

DATA_PLACEHOLDER = "/*__BAUPLAN_DATA__*/null"
ECHARTS_PLACEHOLDER = "/*__ECHARTS__*/"
TEMPLATE_NAME = "template.html"
ECHARTS_FILE = "vendor/echarts.min.js"
"""ECharts 5.5.1 (Apache-2.0), taken from the npm package after checking its registry integrity."""


def render_dashboard(dataset: dict[str, Any]) -> str:
    package = resources.files(__package__)
    template = package.joinpath(TEMPLATE_NAME).read_text(encoding="utf-8")
    echarts = package.joinpath(ECHARTS_FILE).read_text(encoding="utf-8")
    return template.replace(ECHARTS_PLACEHOLDER, _inline_script(echarts)).replace(
        DATA_PLACEHOLDER, _to_script_json(dataset)
    )


def _inline_script(source: str) -> str:
    return source.replace("</script", "<\\/script")


def _to_script_json(dataset: dict[str, Any]) -> str:
    """JSON that is safe inside <script>: bank text could otherwise contain `</script>`."""
    text = json.dumps(dataset, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
