"""V21 zero-cost presentation normalization for persisted AI plans."""
from __future__ import annotations
from copy import deepcopy
from services.v20_presentation import prepare_v20_site

LEGACY_LAYOUT={
 "services":{"container":"standard","density":"compact","alignment":"left","image_ratio":"landscape","emphasis":"strong"},
 "proof":{"container":"standard","density":"balanced","alignment":"left","image_ratio":"landscape","emphasis":"strong"},
 "gallery":{"container":"wide","density":"balanced","alignment":"left","image_ratio":"landscape","emphasis":"strong"},
 "process":{"container":"standard","density":"compact","alignment":"left","image_ratio":"landscape","emphasis":"standard"},
 "faq":{"container":"standard","density":"compact","alignment":"split","image_ratio":"landscape","emphasis":"standard"},
 "service_area":{"container":"standard","density":"compact","alignment":"left","image_ratio":"landscape","emphasis":"standard"},
 "cta":{"container":"standard","density":"compact","alignment":"left","image_ratio":"landscape","emphasis":"strong"},
}

def prepare_v21_site(site:dict)->dict:
    s=prepare_v20_site(deepcopy(site or {}))
    design=s.setdefault("design",{})
    design.setdefault("container_width","standard"); design.setdefault("density","balanced")
    for sec in s.get("sections") or []:
        if not isinstance(sec,dict):continue
        base=dict(LEGACY_LAYOUT.get(sec.get("type"),{"container":"standard","density":"balanced","alignment":"left","image_ratio":"landscape","emphasis":"standard"}))
        incoming=sec.get("layout") if isinstance(sec.get("layout"),dict) else {}
        base.update({k:v for k,v in incoming.items() if v})
        sec["layout"]=base
    s["render_version"]="21.0"
    return s
