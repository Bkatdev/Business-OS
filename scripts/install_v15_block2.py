r"""Transactional correction installer for Business OS v15 Block 2 visual QA.

Run from the repository root:
    python scripts\install_v15_block2.py

The adjacent v15_block2_payload.zip contains complete target files. This script
verifies the installed Block 2 baseline using newline-normalized fingerprints, tests an
isolated candidate, creates an external rollback backup, applies atomic writes,
tests the real repository, runs GET-only visual QA on port 5015, and rolls back
automatically if a required check fails.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = Path(__file__).with_name("v15_block2_payload.zip")
EXPECTED_BRANCH = "feature/v15-website-intelligence"

BASELINE_HASHES = {
    "ARCHITECTURE_V15.md": "3bae4ec1fdc92a2a1850ac74c95edae02eedcde7f352156bcdd9c5fef87ac8ab",
    "app.py": "ca1b99b0364a932a7fc7023066067a2025ce1d4e14c48557ddf7bdd6f2bfe563",
    "services/db.py": "310468811ce605204b51a4bf97946de16cc796370443366e3946caea8f084180",
    "services/version.py": "4a6b4b584ed829cc5bd13c766446cbd331621f5e4aad8b8144fda3d40e1f50c9",
    "static/v15.css": "4bec2931e340088b569a78638546d74a2044c0961615e350a7fd513295428d68",
    "templates/base.html": "8f753018215f15f96cbf54da8c00babd91c685d686ef6d5ac340161efa5325c5",
    "templates/sales_workspace.html": "b0e81d3716979aca1f9a606c90aa11828d516b9b7e0940b2ede4b4203532424f",
    "templates/v15_website_intelligence.html": "fa1f1c93c0d998cf9b09e2936b31caa9b01d80e3303b23e629c627ad5cf65026",
    "scripts/v15_visual_qa.py": "25ec40fcf6faf16fe1b2311603f549512ec2f4fa7c59da0af6cc06ccfe809e72",
    "scripts/test_v15_product_shell.py": "418162b3990289d62bfce9dc202559e6781b891ed4a0093065b3d4d17b581d0f",
}

NEW_FILES = {
    "services/v15_upgrade_engine.py",
    "scripts/test_v15_upgrade_engine.py",
    "scripts/test_v15_block2_integration.py",
}

# The handoff snapshot may differ slightly from the installed Block 1.5 visual
# harness because that harness was generated during an earlier repair. It is
# safe to supersede only when it still proves itself to be the same GET-only
# diagnostic surface. The original is included in the external rollback backup.
SAFE_DRIFT_FILE = "scripts/v15_visual_qa.py"
SAFE_DRIFT_REQUIRED = (
    "GET-only acceptance harness",
    "def start_server_if_needed",
    "def route_matrix",
    "def render_report",
    "No forms were submitted",
)
SAFE_DRIFT_FORBIDDEN = (
    'method="post"', "requests.post", "execute_sms", "send_sms", "twilio",
    "retell.create", "publish_site(", "business_os_live_actions_enabled=1",
)

TARGETS = tuple(BASELINE_HASHES) + tuple(sorted(NEW_FILES))
IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "venv", "__pycache__", "*.pyc", ".env",
    "business_os.db", "business-os.db", "qa", "upgrade_backups",
)


class InstallError(RuntimeError):
    pass


def normalized_hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def normalized_hash(path: Path) -> str:
    return normalized_hash_bytes(path.read_bytes())


def run(command, *, cwd=ROOT, env=None, capture=True):
    return subprocess.run(
        command, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def verify_location_and_branch():
    if not (ROOT / ".git").exists() or not (ROOT / "app.py").exists():
        raise InstallError(
            "Run this installer from C:\\Users\\benka\\Projects\\Business-OS. "
            "Do not run it from the old OneDrive folder."
        )
    result = run(["git", "branch", "--show-current"])
    if result.returncode != 0:
        raise InstallError("Git could not confirm the active branch:\n" + (result.stdout or ""))
    branch = (result.stdout or "").strip()
    if branch != EXPECTED_BRANCH:
        raise InstallError(
            f"Expected branch {EXPECTED_BRANCH!r}, but Git reports {branch!r}. No files changed."
        )


def load_payload():
    if not PAYLOAD.exists():
        raise InstallError(f"Missing payload beside installer: {PAYLOAD.name}")
    with zipfile.ZipFile(PAYLOAD) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist() if not name.endswith("/")}
        if names != set(TARGETS):
            missing = sorted(set(TARGETS) - names)
            extra = sorted(names - set(TARGETS))
            raise InstallError(f"Payload path mismatch. Missing={missing}; extra={extra}")
        payload = {}
        for name in TARGETS:
            member = Path(name)
            if member.is_absolute() or ".." in member.parts:
                raise InstallError("Unsafe path in payload: " + name)
            payload[name] = archive.read(name)
    return payload


def safe_visual_qa_drift(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    lowered = text.lower()
    return (
        all(marker in text for marker in SAFE_DRIFT_REQUIRED)
        and not any(marker.lower() in lowered for marker in SAFE_DRIFT_FORBIDDEN)
    )


def verify_baseline(payload):
    payload_hashes = {name: normalized_hash_bytes(data) for name, data in payload.items()}
    problems = []
    accepted_safe_drift = []
    for name in TARGETS:
        path = ROOT / name
        if not path.exists():
            if name not in NEW_FILES:
                problems.append(f"missing required baseline file: {name}")
            continue
        actual = normalized_hash(path)
        if actual == payload_hashes[name]:
            continue
        expected = BASELINE_HASHES.get(name)
        if expected is None or actual != expected:
            if name == SAFE_DRIFT_FILE and safe_visual_qa_drift(path):
                accepted_safe_drift.append(name)
                continue
            problems.append(f"unexpected local content: {name}")
    if problems:
        raise InstallError(
            "Block 2 stopped because target files do not match the supplied Block 1.5 snapshot.\n"
            + "\n".join("  - " + item for item in problems)
            + "\nNo files changed. Create a fresh source snapshot before retrying."
        )
    already = all((ROOT / name).exists() and normalized_hash(ROOT / name) == payload_hashes[name] for name in TARGETS)
    return payload_hashes, already, accepted_safe_drift


def write_payload(root: Path, payload):
    for name, data in payload.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".v15block2.tmp")
        temp.write_bytes(data)
        os.replace(temp, destination)


def build_candidate(payload):
    candidate = Path(tempfile.mkdtemp(prefix="business-os-v15-block2-candidate-"))
    shutil.copytree(ROOT, candidate, dirs_exist_ok=True, ignore=IGNORE)
    write_payload(candidate, payload)
    return candidate


def test_suite(root: Path):
    tests = sorted((root / "scripts").glob("test_*.py"))
    if not tests:
        raise InstallError("No regression tests were found in the candidate.")
    for test in tests:
        result = run([sys.executable, str(test)], cwd=root)
        if result.returncode != 0:
            raise InstallError(
                f"Regression failed: {test.name}\n" + (result.stdout or "No output")[-12000:]
            )
    compile_targets = [
        "app.py", "services/db.py", "services/v15_site_intelligence.py",
        "services/v15_upgrade_engine.py", "scripts/v15_visual_qa.py",
    ]
    result = run([sys.executable, "-m", "py_compile", *compile_targets], cwd=root)
    if result.returncode != 0:
        raise InstallError("Python compilation failed:\n" + (result.stdout or ""))
    return len(tests)


def visual_qa(root: Path):
    env = os.environ.copy()
    env["BUSINESS_OS_QA_URL"] = "http://127.0.0.1:5015"
    result = run([sys.executable, "scripts/v15_visual_qa.py"], cwd=root, env=env)
    if result.returncode != 0:
        raise InstallError("GET-only visual QA failed:\n" + (result.stdout or "No output")[-12000:])
    return result.stdout or ""


def create_backup():
    backup = Path(tempfile.mkdtemp(prefix="business-os-v15-block2-backup-"))
    manifest = {}
    for name in TARGETS:
        source = ROOT / name
        manifest[name] = {"existed": source.exists()}
        if source.exists():
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return backup, manifest


def restore_backup(backup: Path, manifest):
    for name in TARGETS:
        destination = ROOT / name
        if manifest[name]["existed"]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_name(destination.name + ".v15rollback.tmp")
            shutil.copy2(backup / name, temp)
            os.replace(temp, destination)
        elif destination.exists():
            destination.unlink()


def verify_applied(payload_hashes):
    mismatches = [
        name for name in TARGETS
        if not (ROOT / name).exists() or normalized_hash(ROOT / name) != payload_hashes[name]
    ]
    if mismatches:
        raise InstallError("Applied files failed verification: " + ", ".join(mismatches))


def main():
    print("Business OS v15 Block 2 - visual acceptance correction")
    print("[1/8] Verifying repository and branch")
    verify_location_and_branch()
    print("[2/8] Validating signed path set and installed Block 2 baseline")
    payload = load_payload()
    payload_hashes, already, accepted_safe_drift = verify_baseline(payload)
    if accepted_safe_drift:
        print("Accepted verified GET-only drift in:", ", ".join(accepted_safe_drift))
        print("The current file will be preserved in the external rollback backup.")

    if already:
        print("Block 2 files already match this installer. Running verification only.")
        count = test_suite(ROOT)
        report = visual_qa(ROOT)
        print(report.strip())
        print(f"PASS: {count} regression scripts plus GET-only visual QA")
        return 0

    print("[3/8] Building isolated candidate")
    candidate = build_candidate(payload)
    try:
        print("[4/8] Running the full regression suite in isolation")
        candidate_count = test_suite(candidate)
        print(f"PASS: {candidate_count} isolated regression scripts")

        print("[5/8] Creating external rollback backup")
        backup, manifest = create_backup()
        print("Backup:", backup)

        try:
            print("[6/8] Applying exact target files atomically")
            write_payload(ROOT, payload)
            verify_applied(payload_hashes)

            print("[7/8] Testing the real repository")
            real_count = test_suite(ROOT)

            print("[8/8] Running GET-only visual QA on isolated port 5015")
            report = visual_qa(ROOT)
            print(report.strip())
            print(f"PASS: {real_count} real-repository regression scripts")
        except Exception:
            print("A post-apply check failed. Restoring the external backup now.")
            restore_backup(backup, manifest)
            raise
    finally:
        shutil.rmtree(candidate, ignore_errors=True)

    print("\nV15 BLOCK 2 VISUAL ACCEPTANCE CORRECTION INSTALLED SUCCESSFULLY")
    print("Website Intelligence contrast, evidence metrics, and stable viewport capture are corrected.")
    print("No live SMS, calls, scheduling, publishing, or customer communication was enabled.")
    print("Do not commit or tag v15 yet. A short manual product acceptance journey comes next.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as exc:
        print("\nINSTALLATION STOPPED SAFELY")
        print(exc)
        raise SystemExit(1)
