from pathlib import Path
import re
import sys
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"PASS · {name}{' · ' + detail if detail else ''}")
    else:
        print(f"FAIL · {name}{' · ' + detail if detail else ''}")
        FAILURES.append(name)

version = (ROOT / "services" / "version.py").read_text(encoding="utf-8")
check("Version identity", 'VERSION = "v11.1"' in version and 'RELEASE_NAME = "Operator Polish"' in version)

base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
check("v11.1 visual layer", "v111.css" in base)
check("Client configuration nav continuity", "business_configuration" in base and "toggle_business_intake_question" in base)

# Every full-page template should inherit the canonical shell.
exceptions = {"base.html", "_table.html"}
missing_shell = []
for template in sorted((ROOT / "templates").glob("*.html")):
    if template.name in exceptions:
        continue
    text = template.read_text(encoding="utf-8").lstrip()
    if "{% extends" not in text[:120]:
        missing_shell.append(template.name)
check("Canonical shell coverage", not missing_shell, f"missing={missing_shell}")

# Parse every template so polish changes cannot ship malformed Jinja.
env = Environment()
parse_errors = []
for template in sorted((ROOT / "templates").glob("*.html")):
    try:
        env.parse(template.read_text(encoding="utf-8"))
    except Exception as exc:
        parse_errors.append(f"{template.name}: {exc}")
check("Template parse", not parse_errors, f"errors={parse_errors}")

prospects = (ROOT / "templates" / "prospects.html").read_text(encoding="utf-8")
check("Industry-neutral prospect defaults", 'value="tree service near East Brunswick, New Jersey"' not in prospects and 'value="Tree Care"' not in prospects)

client = (ROOT / "templates" / "client_command_center.html").read_text(encoding="utf-8")
check("Client schedule count uses real appointment count", "product.counts.appointments }} tracked" in client and "schedule|length" not in client)

approvals = (ROOT / "templates" / "approvals.html").read_text(encoding="utf-8")
app = (ROOT / "app.py").read_text(encoding="utf-8")
check("Unified approval visibility", "message_approvals" in approvals and "message_approvals=message_rows" in app)
check("Message authority remains in Automation", "Review in Automation" in approvals and "approve_message" not in approvals)
check("General approval controls preserved", "approval_action" in approvals and "action='approve'" in approvals and "action='reject'" in approvals)

agents = (ROOT / "templates" / "agents.html").read_text(encoding="utf-8")
check("Agent Center distinguishes available vs planned", "Available" in agents and "Planned" in agents and "No production capability exposed" in agents)

css = (ROOT / "static" / "v111.css").read_text(encoding="utf-8")
check("Operator polish responsive CSS", "@media(max-width:900px)" in css and "@media(max-width:620px)" in css)

# v11 safety must remain intact; this pass must not expose a new live execution route/provider.
route_text = "\n".join(re.findall(r'@app\.route\([^\n]+', app))
check("No live execution route added", "/live" not in route_text.lower() and "execute-live" not in route_text.lower())
provider_init = ROOT / "services" / "providers" / "__init__.py"
provider_text = provider_init.read_text(encoding="utf-8") if provider_init.exists() else ""
check("No live provider added", "Twilio" not in provider_text and "live_provider" not in provider_text.lower())

if FAILURES:
    print(f"\nBusiness OS v11.1 verification FAILED · {len(FAILURES)} issue(s)")
    sys.exit(1)
print("\nBusiness OS v11.1 verification PASS")
