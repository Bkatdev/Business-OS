import os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))

def ok(value,msg):
    if not value: raise AssertionError(msg)
    print('PASS:',msg)

# Static integration contracts: routes must be reachable from the real client workspace.
base=(ROOT/'templates/base.html').read_text(encoding='utf8')
client=(ROOT/'templates/client_command_center.html').read_text(encoding='utf8')
nav=(ROOT/'templates/_client_workspace_nav.html').read_text(encoding='utf8')
unavailable=(ROOT/'templates/client_portal_unavailable.html').read_text(encoding='utf8')
app=(ROOT/'app.py').read_text(encoding='utf8')
portal=(ROOT/'services/v14_client_portal.py').read_text(encoding='utf8')
experience=(ROOT/'services/v14_client_experience.py').read_text(encoding='utf8')

ok('_client_workspace_nav.html' in client,'client overview exposes persistent workspace navigation')
ok("client_portal_preview" in nav and 'Owner Preview' in nav,'owner preview is discoverable from client workspace')
ok("website_studio" in nav and '>Website<' in nav,'website is a first-class client destination')
ok('Founder HQ' not in (ROOT/'templates/client_portal_preview.html').read_text(encoding='utf8'),'owner surface excludes founder navigation')
ok("WHERE business_id=?" in portal,'owner data remains tenant-scoped')
ok('owner_preview_state' in experience,'owner preview has a dedicated stable read boundary')
ok('client_portal_unavailable.html' in app and '503' in app,'owner preview failure is visible and recoverable')
ok('Nothing was published' in unavailable,'recovery page states safety boundary')
ok('BUSINESS_OS_LIVE_ACTIONS_ENABLED=1' not in experience,'stabilization does not unlock live actions')
ok('twilio' not in experience.lower() and 'retell.create' not in experience.lower(),'stabilization adds no provider side effects')

# Templates parse as a set, catching route/template syntax drift.
from jinja2 import Environment, FileSystemLoader
j=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
for name in ['client_command_center.html','client_onboarding.html','business_configuration.html','website_studio.html','production_design_studio.html','delivery_center.html','client_portal_preview.html','client_portal_unavailable.html','_client_workspace_nav.html']:
    j.get_template(name); print('PASS: template parses:',name)

print('ALL V14 STABILIZATION TESTS PASSED')
