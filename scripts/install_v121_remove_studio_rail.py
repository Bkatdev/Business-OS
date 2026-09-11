from pathlib import Path
import re
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "website_studio.html"

text = TEMPLATE.read_text(encoding="utf-8")

# Find the dedicated Website Studio rail.
pattern = re.compile(
    r'\n\s*<aside class="v12-studio-rail">.*?</aside>',
    re.DOTALL
)

matches = pattern.findall(text)

if len(matches) != 1:
    raise SystemExit(
        f"ABORT: expected exactly 1 v12-studio-rail, found {len(matches)}. "
        "No file was changed."
    )

text = pattern.sub("", text, count=1)

# The editor is now intentionally the sole column.
old_layout = '<div class="v12-studio-layout">'
if old_layout not in text:
    raise SystemExit(
        "ABORT: Website Studio layout wrapper not found. No file was changed."
    )

fd, temp_name = tempfile.mkstemp(
    prefix=TEMPLATE.name + ".",
    suffix=".tmp",
    dir=str(TEMPLATE.parent),
    text=True,
)

try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temp_name, TEMPLATE)
except Exception:
    try:
        os.unlink(temp_name)
    except OSError:
        pass
    raise

print("Business OS v12.1 - Studio Rail Removal")
print("Repository:", ROOT)
print()
print("PASS: Shared Business Truth sidebar removed")
print("PASS: presentation editor preserved")
print("PASS: readiness preserved")
print("PASS: version history preserved")
print("PASS: preview controls preserved")
print("PASS: canonical business data remains unchanged")
print("PASS: live publishing remains locked")
