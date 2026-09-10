from pathlib import Path
import py_compile
import shutil
import tempfile
import sys

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app.py'
SERVICE = ROOT / 'services' / 'action_queue.py'
DASH = ROOT / 'templates' / 'dashboard.html'
CSS = ROOT / 'static' / 'styles.css'

print()
print('======================================')
print(' BUSINESS OS ACTION QUEUE')
print('======================================')
print()

for p in (APP, DASH, CSS):
    if not p.exists():
        raise FileNotFoundError(f'Required file not found: {p}')

backup = Path(tempfile.mkdtemp(prefix='business_os_action_queue_'))
for p in (APP, DASH, CSS):
    dest = backup / p.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
if SERVICE.exists():
    dest = backup / SERVICE.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVICE, dest)

print('Safety backup created:')
print(backup)
print()

service_text = '''from datetime import datetime

CLOSED_STATUSES = {"Won", "Lost"}

def _value(row, key, default=""):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = default
    return default if value is None else value

def _parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None

def _hours_since(value):
    ts = _parse_datetime(value)
    if ts is None:
        return 0
    try:
        now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
        seconds = (now - ts).total_seconds()
    except (TypeError, ValueError):
        return 0
    return max(0, int(seconds // 3600))

def _age_label(hours):
    if hours <= 0:
        return "Updated recently"
    if hours == 1:
        return "1 hour since activity"
    if hours < 24:
        return f"{hours} hours since activity"
    days = hours // 24
    return "1 day since activity" if days == 1 else f"{days} days since activity"

def _recommendation(status, priority, safety_flag, preferred_time):
    if priority == "Urgent" or safety_flag:
        return ("Urgent", "urgent", "Escalate to owner", safety_flag or "This lead was marked urgent.", 1000)
    if status == "New":
        reason = (f"Customer prefers {preferred_time} and has not been contacted yet." if preferred_time else "New opportunity has not been contacted yet.")
        return ("High", "high", "Contact lead", reason, 800)
    if status == "Contacted":
        reason = (f"Customer has been contacted and prefers {preferred_time}." if preferred_time else "Customer has been contacted but the opportunity is still open.")
        return ("Follow Up", "follow-up", "Continue follow-up", reason, 650)
    if status == "Estimate Scheduled":
        return ("Scheduled", "scheduled", "Review scheduled estimate", "An estimate is scheduled and the opportunity remains open.", 450)
    return ("Open", "open", "Review lead", "This opportunity is still open and should be reviewed.", 250)

def build_action_queue(leads, limit=8):
    queue = []
    for lead in leads:
        status = str(_value(lead, "status", "New")).strip()
        if status in CLOSED_STATUSES:
            continue
        priority = str(_value(lead, "priority", "Normal")).strip()
        safety_flag = str(_value(lead, "safety_flag", "")).strip()
        preferred_time = str(_value(lead, "preferred_time", "")).strip()
        last_activity = _value(lead, "last_activity_at", "") or _value(lead, "created_at", "")
        hours = _hours_since(last_activity)
        level, level_class, next_action, reason, base_score = _recommendation(status, priority, safety_flag, preferred_time)
        queue.append({
            "id": _value(lead, "id", 0),
            "caller_name": _value(lead, "caller_name", "") or "Unknown Caller",
            "service_type": _value(lead, "service_type", "") or "Service request",
            "status": status,
            "next_action": next_action,
            "reason": reason,
            "level": level,
            "level_class": level_class,
            "age_label": _age_label(hours),
            "score": base_score + min(hours, 240),
        })
    queue.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return queue[:limit]
'''

SERVICE.parent.mkdir(parents=True, exist_ok=True)
SERVICE.write_text(service_text, encoding='utf-8')

app = APP.read_text(encoding='utf-8')
start = app.find('def dashboard():')
if start == -1:
    raise RuntimeError('Could not find dashboard() in app.py.')
end = app.find('\n@app.route', start + 1)
if end == -1:
    end = len(app)
block = app[start:end]

if 'from services.action_queue import build_action_queue' not in block:
    old = 'def dashboard():\n    conn = connect()\n'
    new = 'def dashboard():\n    from services.action_queue import build_action_queue\n\n    conn = connect()\n'
    if old not in block:
        raise RuntimeError('Could not safely insert Action Queue import.')
    block = block.replace(old, new, 1)

if 'action_queue_rows = conn.execute(' not in block:
    old = '\n    conn.close()\n'
    new = '''
    action_queue_rows = conn.execute(
        """
        SELECT
            leads.*,
            businesses.name AS business_name,
            (
                SELECT MAX(lead_activities.created_at)
                FROM lead_activities
                WHERE lead_activities.lead_id = leads.id
            ) AS last_activity_at
        FROM leads
        LEFT JOIN businesses
            ON businesses.id = leads.business_id
        WHERE leads.status NOT IN ('Won', 'Lost')
        ORDER BY leads.id DESC
        """
    ).fetchall()

    conn.close()
'''
    if old not in block:
        raise RuntimeError('Could not find dashboard database close point.')
    block = block.replace(old, new, 1)

if 'action_queue = build_action_queue(' not in block:
    old = '\n    return render_template(\n'
    new = '''
    action_queue_total = len(action_queue_rows)
    action_queue = build_action_queue(action_queue_rows, limit=8)
    top_action = action_queue[0] if action_queue else None

    return render_template(
'''
    if old not in block:
        raise RuntimeError('Could not find dashboard render point.')
    block = block.replace(old, new, 1)

if 'action_queue=action_queue' not in block:
    old = '        urgent_leads=urgent_leads,\n        pipeline=pipeline,\n'
    new = '        urgent_leads=urgent_leads,\n        action_queue=action_queue,\n        action_queue_total=action_queue_total,\n        top_action=top_action,\n        pipeline=pipeline,\n'
    if old not in block:
        raise RuntimeError('Could not add Action Queue template variables.')
    block = block.replace(old, new, 1)

APP.write_text(app[:start] + block + app[end:], encoding='utf-8')

dash = DASH.read_text(encoding='utf-8')
if 'BUSINESS OS ACTION QUEUE' not in dash:
    marker = '    <div class="dashboard-main">\n'
    html = '''    <div class="dashboard-main">\n\n        <!-- BUSINESS OS ACTION QUEUE -->\n        <div class="panel command-panel action-queue-panel">\n            <div class="panel-heading">\n                <div>\n                    <span class="section-kicker">NEXT ACTIONS</span>\n                    <h3>Action Queue</h3>\n                </div>\n                <span class="count-bubble">{{ action_queue_total }}</span>\n            </div>\n\n            {% if top_action %}\n            <div class="action-queue-summary">\n                <span class="action-summary-label">DO THIS FIRST</span>\n                <strong>{{ top_action["next_action"] }}</strong>\n                <span>{{ top_action["caller_name"] }} · {{ top_action["service_type"] }}</span>\n            </div>\n            {% endif %}\n\n            {% if action_queue %}\n            <div class="action-queue-list">\n                {% for item in action_queue %}\n                <a class="action-queue-item" href="{{ url_for('lead_detail', lead_id=item['id']) }}">\n                    <div class="action-rank">{{ loop.index }}</div>\n                    <div class="action-queue-body">\n                        <div class="action-queue-title">\n                            <strong>{{ item["caller_name"] }}</strong>\n                            <span class="action-level {{ item['level_class'] }}">{{ item["level"] }}</span>\n                        </div>\n                        <div class="action-service">{{ item["service_type"] }} · {{ item["status"] }}</div>\n                        <div class="action-next">{{ item["next_action"] }}</div>\n                        <div class="action-reason">{{ item["reason"] }}</div>\n                        <div class="action-age">{{ item["age_label"] }}</div>\n                    </div>\n                    <div class="action-arrow">→</div>\n                </a>\n                {% endfor %}\n            </div>\n            {% else %}\n            <div class="clear-state">\n                <span class="clear-check">✓</span>\n                <div>\n                    <strong>Action queue is clear</strong>\n                    <p>There are no open leads requiring attention.</p>\n                </div>\n            </div>\n            {% endif %}\n        </div>\n'''
    if marker not in dash:
        raise RuntimeError('Could not find dashboard-main container.')
    dash = dash.replace(marker, html, 1)
DASH.write_text(dash, encoding='utf-8')

css = CSS.read_text(encoding='utf-8')
if 'BUSINESS OS ACTION QUEUE' not in css:
    css += '''\n\n/* BUSINESS OS ACTION QUEUE */\n.action-queue-panel { overflow: hidden; }\n.action-queue-summary { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; margin-bottom:18px; padding:14px 16px; border:1px solid rgba(17,94,89,.16); border-radius:14px; background:rgba(17,94,89,.055); }\n.action-summary-label { font-size:.68rem; font-weight:800; letter-spacing:.09em; text-transform:uppercase; opacity:.68; }\n.action-queue-list { display:flex; flex-direction:column; }\n.action-queue-item { display:grid; grid-template-columns:34px minmax(0,1fr) 24px; gap:12px; align-items:flex-start; padding:15px 4px; border-top:1px solid rgba(15,23,42,.08); color:inherit; text-decoration:none; transition:transform .16s ease; }\n.action-queue-item:first-child { border-top:0; }\n.action-queue-item:hover { transform:translateX(2px); }\n.action-rank { display:flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:10px; background:rgba(15,23,42,.06); font-size:.78rem; font-weight:800; }\n.action-queue-title { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-bottom:3px; }\n.action-level { display:inline-flex; align-items:center; min-height:22px; padding:3px 8px; border-radius:999px; background:rgba(15,23,42,.07); font-size:.67rem; font-weight:800; }\n.action-level.urgent { background:rgba(185,28,28,.10); }\n.action-level.high { background:rgba(180,83,9,.10); }\n.action-level.follow-up { background:rgba(37,99,235,.09); }\n.action-level.scheduled { background:rgba(5,150,105,.09); }\n.action-service { margin-bottom:8px; font-size:.78rem; opacity:.64; }\n.action-next { margin-bottom:4px; font-size:.87rem; font-weight:750; }\n.action-reason { max-width:680px; font-size:.79rem; line-height:1.45; opacity:.76; }\n.action-age { margin-top:7px; font-size:.7rem; font-weight:650; opacity:.5; }\n.action-arrow { padding-top:4px; font-size:1rem; opacity:.48; }\n@media (max-width:680px) { .action-queue-summary { align-items:flex-start; flex-direction:column; } .action-queue-item { grid-template-columns:30px minmax(0,1fr) 18px; gap:9px; } }\n'''
CSS.write_text(css, encoding='utf-8')

try:
    py_compile.compile(str(APP), doraise=True)
    py_compile.compile(str(SERVICE), doraise=True)
    print('Python validation: PASS')
except Exception as exc:
    print('Python validation: FAIL')
    print(exc)
    print('Backup:', backup)
    sys.exit(1)

try:
    from jinja2 import Environment
    Environment().parse(DASH.read_text(encoding='utf-8'))
    print('Template validation: PASS')
except Exception as exc:
    print('Template validation: FAIL')
    print(exc)
    print('Backup:', backup)
    sys.exit(1)

print()
print('======================================')
print(' ACTION QUEUE UPGRADE COMPLETE')
print('======================================')
print()
print('Updated:')
print('  app.py')
print('  services/action_queue.py')
print('  templates/dashboard.html')
print('  static/styles.css')
print()
print('Next: Restart Flask, open the dashboard, and test the Action Queue.')
print('Do not delete this script yet.')
