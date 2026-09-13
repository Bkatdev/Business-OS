"""Business OS v15 local visual QA.

GET-only acceptance harness. It never submits forms or invokes provider actions.
It can start the local Flask app, discover useful routes from the local development
database, capture desktop/tablet/phone screenshots, and write one HTML report.
"""
from __future__ import annotations

import html
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("BUSINESS_OS_QA_URL", "http://127.0.0.1:5000").rstrip("/")
OUT = ROOT / "qa" / "v15" / datetime.now().strftime("%Y%m%d-%H%M%S")
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = {
    "desktop": (1440, 1000),
    "tablet": (1024, 900),
    "phone": (390, 844),
}

def http_status(path: str, timeout=8):
    req = urllib.request.Request(BASE_URL + path, headers={"User-Agent": "BusinessOS-VisualQA/15"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.geturl(), ""
    except urllib.error.HTTPError as exc:
        return exc.code, exc.geturl(), str(exc)
    except Exception as exc:
        return 0, BASE_URL + path, f"{type(exc).__name__}: {exc}"

def reachable():
    return http_status("/", timeout=2)[0] == 200

def start_server_if_needed():
    if reachable():
        return None
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    parsed = urlparse(BASE_URL)
    if parsed.port:
        env["BUSINESS_OS_PORT"] = str(parsed.port)
    proc = subprocess.Popen(
        [sys.executable, "app.py"], cwd=ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        time.sleep(.35)
        if reachable():
            return proc
    proc.terminate()
    raise RuntimeError("Local Business OS did not become reachable at " + BASE_URL)

def db_path():
    for name in ("business_os.db", "business-os.db"):
        p = ROOT / name
        if p.exists():
            return p
    return None

def table_exists(conn, name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())

def discover_context():
    result = {
        "prospect_id": None, "client_id": None, "slug": None,
        "intelligence_run_id": None, "blueprint_id": None,
    }
    path = db_path()
    if not path:
        return result
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(businesses)")}
        if {"id", "website"}.issubset(cols):
            row = None
            if table_exists(conn, "upgrade_blueprints"):
                row = conn.execute(
                    "SELECT b.id, u.id AS blueprint_id, u.intelligence_run_id "
                    "FROM upgrade_blueprints u JOIN businesses b ON b.id=u.business_id "
                    "WHERE COALESCE(b.website,'') <> '' ORDER BY u.id DESC LIMIT 1"
                ).fetchone()
            if row:
                result["prospect_id"] = row["id"]
                result["blueprint_id"] = row["blueprint_id"]
                result["intelligence_run_id"] = row["intelligence_run_id"]
            elif table_exists(conn, "site_intelligence_runs"):
                row = conn.execute(
                    "SELECT b.id, r.id AS intelligence_run_id "
                    "FROM site_intelligence_runs r JOIN businesses b ON b.id=r.business_id "
                    "WHERE COALESCE(b.website,'') <> '' ORDER BY r.id DESC LIMIT 1"
                ).fetchone()
                if row:
                    result["prospect_id"] = row["id"]
                    result["intelligence_run_id"] = row["intelligence_run_id"]
            if result["prospect_id"] is None:
                row = conn.execute(
                    "SELECT id FROM businesses WHERE COALESCE(website,'') <> '' "
                    "ORDER BY CASE WHEN id=4 THEN 0 ELSE 1 END,id LIMIT 1"
                ).fetchone()
                if row:
                    result["prospect_id"] = row["id"]
        if {"id", "status"}.issubset(cols):
            row = conn.execute(
                "SELECT id FROM businesses WHERE upper(COALESCE(status,'')) IN "
                "('CLIENT','ONBOARDING','ACTIVE') "
                "ORDER BY CASE WHEN id=4 THEN 0 ELSE 1 END,id LIMIT 1"
            ).fetchone()
            if row:
                result["client_id"] = row["id"]
        if table_exists(conn, "site_release_artifacts"):
            row = conn.execute(
                "SELECT public_slug FROM site_release_artifacts "
                "WHERE is_active=1 ORDER BY deployment_id DESC LIMIT 1"
            ).fetchone()
            if row:
                result["slug"] = row["public_slug"]
    finally:
        conn.close()
    return result

def route_matrix(ctx):
    routes = [
        ("home", "/", True),
        ("founder", "/founder", True),
        ("prospects", "/prospects", True),
        ("clients", "/clients", True),
        ("attention", "/attention", True),
        ("system-health", "/system-health", True),
    ]
    pid = ctx["prospect_id"]
    if pid:
        routes += [
            ("prospect", f"/business/{pid}", True),
            ("website-intelligence", f"/business/{pid}/intelligence", True),
            ("sales-workspace", f"/business/{pid}/sales", False),
        ]
    cid = ctx["client_id"]
    if cid:
        routes += [
            ("client-overview", f"/client/{cid}", True),
            ("client-website", f"/client/{cid}/website", False),
            ("production-design", f"/client/{cid}/design", False),
            ("production-preview", f"/client/{cid}/design/preview", False),
            ("owner-today", f"/client/{cid}/owner-preview?tab=today", False),
            ("owner-leads", f"/client/{cid}/owner-preview?tab=leads", False),
            ("acceptance-lab", f"/client/{cid}/acceptance", False),
            ("configuration", f"/client/{cid}/configuration", False),
        ]
    if ctx["slug"]:
        routes.append(("customer-site", f"/site/{ctx['slug']}", False))
    return routes

def find_browser():
    candidates = [p for p in (os.environ.get("CHROME_PATH"), os.environ.get("EDGE_PATH")) if p]
    if os.name == "nt":
        for base in filter(None, (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA"))):
            candidates.extend([
                str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
            ])
    else:
        for name in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    return next((p for p in candidates if p and Path(p).exists()), None)

def chrome_screenshot(browser, url, output, width, height):
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--disable-extensions", "--no-first-run", "--no-default-browser-check",
        "--force-prefers-reduced-motion", "--run-all-compositor-stages-before-draw",
        "--force-device-scale-factor=1", "--virtual-time-budget=1800",
        f"--window-size={width},{height}", f"--screenshot={output}", url,
    ]
    try:
        done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=25)
        return done.returncode == 0 and Path(output).exists(), (done.stderr or done.stdout)[-500:]
    except Exception as exc:
        return False, str(exc)

def playwright_capture(routes):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    results = []
    with sync_playwright() as pw:
        browser = None
        for launch in (
            lambda: pw.chromium.launch(channel="msedge", headless=True),
            lambda: pw.chromium.launch(channel="chrome", headless=True),
            lambda: pw.chromium.launch(headless=True),
        ):
            try:
                browser = launch()
                break
            except Exception:
                pass
        if browser is None:
            return None
        for label, path, required in routes:
            for vp_name, (width, height) in VIEWPORTS.items():
                page = browser.new_page(
                    viewport={"width": width, "height": height}, reduced_motion="reduce",
                )
                console_errors, page_errors = [], []
                page.on("console", lambda msg, bag=console_errors: bag.append(msg.text) if msg.type == "error" else None)
                page.on("pageerror", lambda exc, bag=page_errors: bag.append(str(exc)))
                status, problem, overflow, shot_name = 0, "", False, ""
                try:
                    response = page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=15000)
                    status = response.status if response else 0
                    page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
                    page.wait_for_timeout(150)
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                    )
                    hidden_reveals = page.evaluate(
                        """() => [...document.querySelectorAll('.page-content .bos-reveal')]
                        .filter((el) => Number.parseFloat(getComputedStyle(el).opacity) < 0.95)
                        .length"""
                    )
                    if hidden_reveals:
                        problem = f"{hidden_reveals} content block(s) remained visually hidden"
                    shot = OUT / f"{label}-{vp_name}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    shot_name = shot.name
                except Exception as exc:
                    problem = f"{type(exc).__name__}: {exc}"
                results.append({
                    "label": label, "path": path, "required": required, "viewport": vp_name,
                    "status": status, "overflow": bool(overflow),
                    "console_errors": console_errors[:5], "page_errors": page_errors[:5],
                    "screenshot": shot_name, "problem": problem,
                })
                page.close()

        page = browser.new_page(
            viewport={"width": 1440, "height": 1000}, reduced_motion="reduce",
        )
        try:
            page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=15000)
            toggle = page.locator("[data-sidebar-toggle]")
            if toggle.count():
                toggle.click()
                page.wait_for_timeout(150)
                box = page.locator(".sidebar").bounding_box()
                sidebar_width = box["width"] if box else 0
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
                )
                clipped_note = page.locator(".sidebar-context-note:visible").count() > 0
                shot = OUT / "home-desktop-collapsed.png"
                page.screenshot(path=str(shot), full_page=True)
                problem = "" if sidebar_width <= 74 and not clipped_note else (
                    f"collapsed width={sidebar_width}, clipped_note={clipped_note}"
                )
                results.append({
                    "label": "collapsed-sidebar", "path": "/", "required": True,
                    "viewport": "desktop", "status": 200, "overflow": bool(overflow),
                    "console_errors": [], "page_errors": [], "screenshot": shot.name,
                    "problem": problem,
                })
        finally:
            page.close()
        browser.close()
    return results

def fallback_capture(routes):
    browser = find_browser()
    results = []
    for label, path, required in routes:
        status, _final_url, error = http_status(path)
        for vp_name, (width, height) in VIEWPORTS.items():
            shot_name, capture_problem = "", ""
            if browser and status and status < 500:
                shot = OUT / f"{label}-{vp_name}.png"
                ok, detail = chrome_screenshot(browser, BASE_URL + path, shot, width, height)
                if ok:
                    shot_name = shot.name
                else:
                    capture_problem = detail
            results.append({
                "label": label, "path": path, "required": required, "viewport": vp_name,
                "status": status, "overflow": None, "console_errors": [],
                "page_errors": [], "screenshot": shot_name,
                "problem": error or capture_problem,
            })
    return results

def render_report(results, context, advanced):
    def flagged(r):
        return (
            (r["required"] and (r["status"] >= 400 or r["status"] == 0))
            or r["overflow"] is True
            or bool(r["console_errors"])
            or bool(r["page_errors"])
            or bool(r["problem"])
            or not r["screenshot"]
        )

    failures = [r for r in results if flagged(r)]
    cards = []
    for r in results:
        bad = flagged(r)
        state = "FAIL" if bad else ("PASS" if r["status"] and r["status"] < 400 else "WARN")
        if r["screenshot"]:
            escaped = html.escape(r["screenshot"])
            shot = f'<a href="{escaped}"><img src="{escaped}" loading="lazy"></a>'
        else:
            shot = '<div class="no-shot">No screenshot</div>'
        details = []
        if r["overflow"] is True:
            details.append("horizontal overflow")
        if r["console_errors"]:
            details.append("console: " + " | ".join(r["console_errors"]))
        if r["page_errors"]:
            details.append("page: " + " | ".join(r["page_errors"]))
        if r["problem"]:
            details.append(r["problem"])
        cards.append(
            '<article class="card {cls}"><div class="meta"><b>{state}</b>'
            '<span>{label} - {vp}</span><code>{path}</code><small>HTTP {status}</small>'
            '</div>{shot}<p>{detail}</p></article>'.format(
                cls=state.lower(), state=state, label=html.escape(r["label"]),
                vp=html.escape(r["viewport"]), path=html.escape(r["path"]),
                status=r["status"] or "ERR", shot=shot,
                detail=html.escape(" | ".join(details)),
            )
        )

    summary = f"{len(results)} renders - {len(failures)} flagged"
    report = '''<!doctype html><html><head><meta charset="utf-8">
<title>Business OS v15 Visual QA</title>
<style>
body{margin:0;background:#f4f6f4;color:#132019;font:14px system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:34px 4vw;background:#10231b;color:white}header h1{font-size:42px;letter-spacing:-.04em;margin:6px 0}
header p{color:#afc0b7}main{padding:28px 4vw 60px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.card{background:#fff;border:1px solid #dde4df;border-radius:16px;overflow:hidden}.card.fail{border-color:#e0aaa3}
.meta{padding:14px;display:grid;grid-template-columns:auto 1fr;gap:5px 10px;align-items:center}.meta b{font-size:11px}
.pass .meta b{color:#0b7650}.fail .meta b{color:#a13f34}code,small{color:#718078;font-size:11px}
img{display:block;width:100%;border-top:1px solid #e5e9e6}.card p{padding:0 14px 14px;color:#8b4f49;font-size:11px}
.no-shot{padding:50px 14px;color:#87938c;border-top:1px solid #e5e9e6}
</style></head><body>
<header><small>BUSINESS OS - V15 LOCAL VISUAL QA</small><h1>__SUMMARY__</h1>
<p>Browser checks: __MODE__. Stable reduced-motion capture. GET-only. No forms submitted.</p>
<p>Context: __CONTEXT__</p></header><main><div class="grid">__CARDS__</div></main></body></html>'''
    report = (
        report.replace("__SUMMARY__", html.escape(summary))
        .replace("__MODE__", "Playwright" if advanced else "HTTP + installed Chrome/Edge fallback")
        .replace("__CONTEXT__", html.escape(str(context)))
        .replace("__CARDS__", "".join(cards))
    )
    path = OUT / "report.html"
    path.write_text(report, encoding="utf-8")
    return path, failures

def main():
    server = None
    try:
        server = start_server_if_needed()
        context = discover_context()
        routes = route_matrix(context)
        results = playwright_capture(routes)
        advanced = results is not None
        if results is None:
            results = fallback_capture(routes)
        report, failures = render_report(results, context, advanced)
        bundle = Path(shutil.make_archive(str(OUT), "zip", root_dir=OUT))
        print(f"Visual QA report: {report}")
        print(f"QA upload ZIP: {bundle}")
        print(f"Routes/renders checked: {len(results)}")
        print(f"Flagged results: {len(failures)}")
        for item in failures[:12]:
            print(f"  - {item['label']} [{item['viewport']}]: HTTP {item['status']} {item['problem']}")
        print("No forms were submitted. No live provider action was invoked.")
        return 1 if any(f["required"] for f in failures) else 0
    finally:
        if server is not None:
            server.terminate()

if __name__ == "__main__":
    raise SystemExit(main())
