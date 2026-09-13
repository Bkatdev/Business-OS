from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'app.py').read_text(encoding='utf-8')
tpl=(root/'templates/prospect_concept.html').read_text(encoding='utf-8')
base=(root/'templates/base.html').read_text(encoding='utf-8')
css=(root/'static/v23_product.css').read_text(encoding='utf-8')
agent=(root/'services/v19_ai_website_agent.py').read_text(encoding='utf-8')
assert 'list_v16_demos' in app
assert 'creative_brief=creative_brief' in app
assert 'Open Current Website' in tpl
assert 'Generate New Website' in tpl
assert 'WEBSITE HISTORY' in tpl
assert 'generate_prospect_concept' not in tpl
assert 'AI WEBSITE DESIGN AGENT v19' not in tpl
assert 'Website Studio' in base
assert "v23_product.css" in base
assert 'creative_brief=""' in agent
assert 'OWNER/OPERATOR CREATIVE DIRECTION' in agent
assert '--bos-brand:' in css and '--bos-sidebar:' in css
print('PASS V23 unified studio: one generator + current website + history + creative direction + unified product tokens')
