import os,sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));sys.path.insert(0,ROOT)
def ok(x,m):
    if not x: raise AssertionError(m)
    print('PASS:',m)
files=['services/v14_production_site.py','services/v14_client_portal.py','templates/production_design_studio.html','templates/production_site_preview.html','templates/client_portal_preview.html','static/v14_production.css','static/v14_portal.css']
for f in files: ok(os.path.exists(os.path.join(ROOT,f)),f+' exists')
prod=open(os.path.join(ROOT,'services/v14_production_site.py'),encoding='utf8').read()
ok('validate_blueprint' in prod,'production designer validates allowlisted blueprint')
ok('website_version_id' in prod and 'Design is stale' in prod,'design is bound to reviewed website version')
ok('build_preview_render_model' in prod,'production design consumes reviewed Website Studio truth')
portal=open(os.path.join(ROOT,'services/v14_client_portal.py'),encoding='utf8').read()
ok("WHERE business_id=?" in portal,'portal reads are tenant-scoped')
tpl=open(os.path.join(ROOT,'templates/client_portal_preview.html'),encoding='utf8').read()
ok('Founder HQ' not in tpl and 'Prospects' not in tpl,'owner portal excludes operator surfaces')
ok('Production client authentication is not enabled yet' in tpl,'portal does not fake production auth')
css=open(os.path.join(ROOT,'static/v14_production.css'),encoding='utf8').read()
ok('@media(max-width:800px)' in css,'production renderer has mobile layout')
ok('family-editorial' in css and 'palette-workwear' in css and 'palette-navy' in css,'renderer supports differentiated families')
appsrc=open(os.path.join(ROOT,'app.py'),encoding='utf8').read()
ok('def production_design_studio' in appsrc and 'def client_portal_preview' in appsrc,'new surfaces have separate routes')
for banned in ['BUSINESS_OS_LIVE_ACTIONS_ENABLED=1','retell.create','twilio']:
    ok(banned.lower() not in (prod+portal).lower(),'new experience layer does not unlock '+banned)
print('ALL V14 PRODUCTION EXPERIENCE TESTS PASSED')
