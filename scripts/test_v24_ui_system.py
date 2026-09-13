from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
base=(ROOT/'templates/base.html').read_text(encoding="utf-8")
v15=(ROOT/'static/v15.css').read_text(encoding="utf-8")
assert 'v22_product.css' not in base and 'v23_product.css' not in base, 'Legacy product override still globally loaded'
assert '--bos-primary:#2563eb' in v15, 'Canonical blue primary token missing'
assert '--bos-success:#15803d' in v15, 'Semantic success token missing'
assert '.v15-page-actions .btn:not(.secondary)' in v15, 'Topbar action specificity fix missing'
assert '.studio-hero' in v15 and '#0b1220' in v15, 'Studio not integrated into canonical system'
assert 'studio-hero h2{color:#fff!important' in v15, 'Studio hero contrast guard missing'
assert 'Business OS design rules' in (ROOT/'templates/prospect_concept.html').read_text(encoding="utf-8"), 'Visible version drift remains in Website Studio'
# customer demos must not inherit base product CSS
for name in ('v19_ai_demo.html','v16_private_demo.html','prospect_concept_preview.html'):
    txt=(ROOT/'templates'/name).read_text(encoding="utf-8")
    assert 'extends "base.html"' not in txt and "extends 'base.html'" not in txt, f'Customer demo {name} inherits Business OS shell'
print('PASS V24 UI system: blue actions + semantic success + hero contrast + studio integration + demo isolation')

