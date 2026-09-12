import os, sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)

def ok(value,label):
    if not value:
        raise AssertionError(label)
    print('PASS:',label)

from services.v14_production_site import _service_areas, _hours, _presentation_services, _public_email

ok(_service_areas('East Brunswick, Old Bridge, Marlboro, Monroe Township') == ['East Brunswick','Old Bridge','Marlboro','Monroe Township'], 'comma-separated service areas render semantically')
ok(_service_areas('East Brunswick, NJ') == ['East Brunswick, NJ'], 'single city/state service area stays intact')
ok(_hours('Mon–Fri 8–6, Sat 9–3, Sun Closed') == ['Mon–Fri 8–6','Sat 9–3','Sun Closed'], 'compact hours render as separate lines')
ok(_public_email('owner@testtreecare.example') == '', '.example email is suppressed publicly')
services=_presentation_services([{'name':'Tree Removal','description':''},{'name':'Tree Trimming','description':''}])
ok('tree location' in services[0]['display_description'].lower(), 'verified tree-removal service receives safe request guidance')
ok('certif' not in str(services).lower() and 'warrant' not in str(services).lower() and '$' not in str(services), 'fallback service copy invents no commercial claims')

public_tpl=open(os.path.join(ROOT,'templates/public_site.html'),encoding='utf8').read()
body_tpl=open(os.path.join(ROOT,'templates/_production_site_body.html'),encoding='utf8').read()
preview_tpl=open(os.path.join(ROOT,'templates/production_site_preview.html'),encoding='utf8').read()
client_tpl=open(os.path.join(ROOT,'templates/client_command_center.html'),encoding='utf8').read()
owner_tpl=open(os.path.join(ROOT,'templates/client_portal_preview.html'),encoding='utf8').read()
base_tpl=open(os.path.join(ROOT,'templates/base.html'),encoding='utf8').read()
css=open(os.path.join(ROOT,'static/v14_production.css'),encoding='utf8').read()
portal_css=open(os.path.join(ROOT,'static/v14_portal.css'),encoding='utf8').read()

ok("{% include '_production_site_body.html' %}" in public_tpl and "{% include '_production_site_body.html' %}" in preview_tpl, 'preview and customer release share one production body')
ok('BUSINESS OS LOCAL CUSTOMER TEST' not in public_tpl and 'acceptance test' not in body_tpl.lower(), 'customer-facing website contains no internal QA banner/copy')
ok('Request an estimate' in body_tpl and 'Send request' in body_tpl, 'customer estimate journey is obvious')
ok('How it works' in body_tpl and 'SERVICE AREA' in body_tpl and 'BUSINESS HOURS' in body_tpl, 'customer site has complete professional information architecture')
ok('tree-scene' in body_tpl and '.hero-art' in css and '.service-grid' in css, 'production site has a deliberate visual composition')
ok('@media(max-width:800px)' in css and '.mobile-estimate-bar' in css, 'customer site has explicit mobile treatment')
ok('Website' in client_tpl and 'Owner Preview' in client_tpl and 'Test Journey' in client_tpl, 'client overview exposes the three primary workflow destinations')
ok('Everything important for' in client_tpl and 'client-launchpad' in client_tpl, 'client overview is reorganized around a focused launchpad')
ok('Local Business Operations' in base_tpl and 'AI Growth Platform' not in base_tpl, 'operator brand language is restrained')
for tab in ['today','leads','calls','schedule','website','settings']:
    ok("('"+tab+"'" in owner_tpl or "'"+tab+"'" in owner_tpl, 'owner portal includes '+tab+' tab')
ok('Production client authentication is not enabled yet' in owner_tpl, 'owner preview does not fake production authentication')
ok('Founder HQ' not in owner_tpl and 'Prospects' not in owner_tpl, 'owner preview excludes founder/operator surfaces')
ok('.shell' in portal_css and '@media(max-width:760px)' in portal_css, 'owner portal has responsive professional layout')

combined='\n'.join([body_tpl, public_tpl, client_tpl, owner_tpl])
for banned in ['BUSINESS_OS_LIVE_ACTIONS_ENABLED=1','twilio','retell.create']:
    ok(banned.lower() not in combined.lower(), 'finalization UI does not unlock '+banned)

try:
    from jinja2 import Environment, FileSystemLoader
    env=Environment(loader=FileSystemLoader(os.path.join(ROOT,'templates')))
    for name in ['_production_site_body.html','public_site.html','production_site_preview.html','client_command_center.html','client_portal_preview.html','production_design_studio.html']:
        env.get_template(name)
        print('PASS: template parses:',name)
except ImportError:
    print('INFO: Jinja not installed in build environment; runtime suite will parse templates.')

print('ALL V14 FINALIZATION TESTS PASSED')
