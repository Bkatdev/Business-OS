"""V20 deterministic presentation QA for persisted AI website plans.
No API calls. Never mutates the saved generation.
"""
from __future__ import annotations
from copy import deepcopy
import re

_META_PATTERNS = [
    r"\bredesign(?:ed)?\b", r"\bconversion path\b", r"\bvisitor(?:s)?\b",
    r"\bwebsite experience\b", r"\bprimary conversion\b", r"\bsurface (?:the|current|available)\b",
    r"\bthe company(?:'s)? existing\b", r"\bplace review proof\b", r"\bdesign(?:ed)? to\b",
    r"\bcontent\b.*\bavailable to prospective\b", r"\bfull review destination\b",
]

def _meta_copy(text: str) -> bool:
    t = str(text or "").strip().lower()
    return bool(t) and any(re.search(p, t) for p in _META_PATTERNS)

def _clean_customer_copy(text):
    text = str(text or "").strip()
    return "" if _meta_copy(text) else text

def prepare_v20_site(site: dict) -> dict:
    """Return a render-only copy with obvious design-note leakage removed.

    This does not invent replacement claims. If copy is internal/meta, it is omitted.
    """
    s = deepcopy(site or {})
    for sec in s.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        sec["body"] = _clean_customer_copy(sec.get("body"))
        for item in sec.get("items") or []:
            if not isinstance(item, dict):
                continue
            item["body"] = _clean_customer_copy(item.get("body"))
            item["meta"] = _clean_customer_copy(item.get("meta"))
    s["render_version"] = "20.0"
    return s
