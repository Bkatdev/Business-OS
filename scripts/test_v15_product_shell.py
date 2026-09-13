import os, sys, ast, importlib.util, tempfile
from pathlib import Path
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)
from jinja2 import Environment, FileSystemLoader

env=Environment(loader=FileSystemLoader(os.path.join(ROOT,"templates")))
for name in (
    "base.html","dashboard.html","founder_command.html","v15_website_intelligence.html",
    "clients.html","prospects.html","client_command_center.html","attention_center.html","system_health.html"
):
    env.parse(open(os.path.join(ROOT,"templates",name),encoding="utf-8").read())

base=open(os.path.join(ROOT,"templates","base.html"),encoding="utf-8").read()
css=open(os.path.join(ROOT,"static","v15.css"),encoding="utf-8").read()
js=open(os.path.join(ROOT,"static","app.js"),encoding="utf-8").read()
intel=open(os.path.join(ROOT,"templates","v15_website_intelligence.html"),encoding="utf-8").read()
dash=open(os.path.join(ROOT,"templates","dashboard.html"),encoding="utf-8").read()
founder=open(os.path.join(ROOT,"templates","founder_command.html"),encoding="utf-8").read()
sales=open(os.path.join(ROOT,"templates","sales_workspace.html"),encoding="utf-8").read()
visual=open(os.path.join(ROOT,"scripts","v15_visual_qa.py"),encoding="utf-8").read()
upgrade=open(os.path.join(ROOT,"services","v15_upgrade_engine.py"),encoding="utf-8").read()

assert "sidebar-context-note" not in base
assert "business-os-v15-shell-collapsed" in js
assert "setupGlobalSearch" in js
assert "v15-search-popover" in base
assert "body.sidebar-collapsed .sidebar-context-note" in css
assert "v15-home-hero" in dash and "See the few things that actually need you." in dash
assert "v15-founder-queue" in founder
assert "v15-evidence-disclosure" in intel
assert "Reference gallery" in intel
assert "rights unverified" in intel.lower()
assert "v15-blueprint-board" in intel
assert "v15-truth-workspace" in intel
assert "v15-sales-upgrade" in sales
assert "CREATE TABLE IF NOT EXISTS upgrade_blueprints" in upgrade
assert "execute_sms" not in upgrade and "publish_site(" not in upgrade
assert 'method="post"' not in visual.lower()
assert "ORDER BY deployment_id DESC" in visual
assert 'env["BUSINESS_OS_PORT"]' in visual
assert "No forms were submitted" in visual
assert "--force-prefers-reduced-motion" in visual
assert "--virtual-time-budget=1800" in visual
assert 'reduced_motion="reduce"' in visual
assert "content block(s) remained visually hidden" in visual
assert 'shutil.make_archive(str(OUT), "zip", root_dir=OUT)' in visual
assert "--force-device-scale-factor=1" in visual
assert ".v15-intel-shell{display:grid" in css
assert ".v15-intel-stats{display:grid" in css
assert ".v15-intel-hero .v15-kicker{color:" in css
assert ".v15-intel-target small,.v15-intel-target strong,.v15-intel-target span{display:block}" in css
ast.parse(visual)

spec=importlib.util.spec_from_file_location("v15_visual_qa_runtime", os.path.join(ROOT,"scripts","v15_visual_qa.py"))
visual_qa=importlib.util.module_from_spec(spec)
spec.loader.exec_module(visual_qa)
with tempfile.TemporaryDirectory(prefix="v15-visual-report-") as temp_dir:
    visual_qa.OUT=Path(temp_dir)
    report,failures=visual_qa.render_report([{
        "label":"home","path":"/","required":True,"viewport":"desktop",
        "status":200,"overflow":False,"console_errors":[],"page_errors":[],
        "screenshot":"","problem":"",
    }], {"prospect_id":None,"client_id":None,"slug":None}, False)
    assert report.exists() and "1 renders - 1 flagged" in report.read_text(encoding="utf-8")
    assert len(failures) == 1
print("ALL V15 PRODUCT SHELL + VISUAL QA TESTS PASSED")
