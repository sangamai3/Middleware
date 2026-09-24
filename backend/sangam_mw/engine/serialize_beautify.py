"""Pretty-print serialized preview text for human-readable panels."""

from __future__ import annotations

import json
import re
from xml.dom import minidom


def beautify_json(text: str, indent: int = 2) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    return json.dumps(parsed, indent=indent, ensure_ascii=False, sort_keys=False) + "\n"


def beautify_xml(text: str, indent: str = "  ") -> str:
    stripped = text.strip()
    if not stripped:
        return text
    try:
        dom = minidom.parseString(stripped.encode("utf-8"))
        pretty = dom.toprettyxml(indent=indent, encoding=None)
        if isinstance(pretty, bytes):
            pretty = pretty.decode("utf-8")
        # Drop extra blank lines minidom adds between nodes
        lines = [ln for ln in pretty.splitlines() if ln.strip()]
        return "\n".join(lines) + "\n"
    except Exception:
        return _indent_xml_fallback(stripped, indent)


def _indent_xml_fallback(text: str, indent: str) -> str:
    """Lightweight tag breaker when XML parser fails."""
    spaced = re.sub(r">\s*<", ">\n<", text.strip())
    depth = 0
    out: list[str] = []
    for line in spaced.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("</"):
            depth = max(0, depth - 1)
        out.append(f"{indent * depth}{line}")
        if line.startswith("<") and not line.startswith("</") and not line.endswith("/>") and "?" not in line[:2]:
            if not line.rstrip().endswith("/>"):
                depth += 1
    return "\n".join(out) + "\n"


def beautify_for_format(text: str, fmt: str) -> str:
    f = (fmt or "").strip().lower().lstrip(".")
    if f == "json":
        return beautify_json(text)
    if f == "xml":
        return beautify_xml(text)
    return text
