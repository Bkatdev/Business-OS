from pathlib import Path
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "website_studio.html"
CSS = ROOT / "static" / "v12.css"

template = TEMPLATE.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. Readiness card
# ------------------------------------------------------------

old_readiness = """    <div class="v12-readiness-card">
        <span>WEBSITE READINESS</span>
        <strong>{{ studio.readiness.score }}%</strong>
        <small>
            {{ studio.readiness.checks|selectattr('passed')|list|length }}
            of
            {{ studio.readiness.checks|length }}
            checks
        </small>
    </div>"""

new_readiness = """    <div class="v12-readiness-card">
        <span>WEBSITE COMPLETENESS</span>
        <strong>{{ studio.readiness.score }}%</strong>
        <small>
            {{ studio.readiness.checks|selectattr('ok')|list|length }}
            of
            {{ studio.readiness.checks|length }}
            details complete
        </small>

        {% if studio.readiness.blockers %}
        <em class="v12-readiness-state needs-attention">
            {{ studio.readiness.blockers|length }}
            required
            {% if studio.readiness.blockers|length == 1 %}item{% else %}items{% endif %}
            still needed
        </em>
        {% else %}
        <em class="v12-readiness-state ready">
            Required website details complete
        </em>
        {% endif %}
    </div>"""

if old_readiness not in template:
    raise SystemExit(
        "ABORT: expected Website Studio readiness block was not found. "
        "No files were changed."
    )

template = template.replace(old_readiness, new_readiness, 1)

# ------------------------------------------------------------
# 2. Owner-facing copy
# ------------------------------------------------------------

copy_replacements = {
    """            Turn verified Business OS information into a professional web presence.
            Services, contact information, service area, and intake remain connected
            to the same canonical business configuration.""":
    """            Build a professional customer-facing website from the business information
            you already manage in Business OS. Update presentation here while services,
            contact details, service area, and customer intake stay connected automatically.""",

    """                        Presentation lives here. Verified business facts stay in
                        Business Configuration.""":
    """                        Shape how the website looks and speaks. Business facts continue
                        to come from your shared Business Configuration.""",

    """                        Saving creates a new immutable version only when something changed.""":
    """                        Saving creates a new draft when something changed, while earlier versions stay available.""",

    """                        Preview selection is explicit. Editing a new draft does not
                        silently replace a reviewed preview.""":
    """                        Choose exactly which version customers would preview. New edits
                        never replace the version you already reviewed.""",

    """                Website Studio can prepare and review a customer-facing experience,
                but v12 does not contain a live publishing provider.""":
    """                Review the customer experience here before any future publishing
                connection is enabled.""",

    """                    No domain, hosting provider, external deployment, SMS,
                    scheduling write, or customer communication is triggered here.""":
    """                    This preview cannot publish a site, send messages, create
                    appointments, or trigger any external customer action."""
}

for old, new in copy_replacements.items():
    if old not in template:
        raise SystemExit(
            "ABORT: expected Website Studio copy block was not found. "
            "No files were changed."
        )
    template = template.replace(old, new, 1)

# ------------------------------------------------------------
# 3. Readiness-state styles
# ------------------------------------------------------------

readiness_anchor = """.v12-readiness-card small{
    color:#89939d;
}
"""

readiness_styles = """.v12-readiness-card small{
    color:#89939d;
}

.v12-readiness-state{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    margin-top:9px;
    padding:5px 8px;
    border-radius:999px;
    font-size:10px;
    font-style:normal;
    font-weight:800;
    line-height:1.25;
}

.v12-readiness-state.needs-attention{
    background:#fff5e8;
    color:#845f1d;
}

.v12-readiness-state.ready{
    background:#effaf4;
    color:#28734a;
}
"""

if readiness_anchor not in css:
    raise SystemExit(
        "ABORT: expected readiness CSS anchor was not found. "
        "No files were changed."
    )

css = css.replace(readiness_anchor, readiness_styles, 1)

# ------------------------------------------------------------
# 4. More resilient Studio grid
# ------------------------------------------------------------

old_layout = """.v12-studio-layout{
    display:grid;
    grid-template-columns:minmax(0,1.65fr) minmax(280px,.7fr);
    gap:18px;
    align-items:start;
}

.v12-editor-column{
    min-width:0;
}
"""

new_layout = """.v12-studio-layout{
    display:grid;
    grid-template-columns:minmax(0,1fr) minmax(300px,340px);
    gap:18px;
    align-items:start;
}

.v12-editor-column,
.v12-studio-rail{
    min-width:0;
}

.v12-studio-rail{
    width:100%;
}
"""

if old_layout not in css:
    raise SystemExit(
        "ABORT: expected Studio layout CSS was not found. "
        "No files were changed."
    )

css = css.replace(old_layout, new_layout, 1)

# ------------------------------------------------------------
# 5. Replace problematic responsive behavior
# ------------------------------------------------------------

old_responsive = """@media(max-width:1000px){

    .v12-studio-layout{
        grid-template-columns:1fr;
    }

    .v12-studio-rail{
        grid-template-columns:repeat(2,minmax(0,1fr));
    }

    .v12-studio-rail .v12-source-card:last-child{
        grid-column:1/-1;
    }

    .v12-public-service-grid{
        grid-template-columns:repeat(2,minmax(0,1fr));
    }
}
"""

new_responsive = """@media(max-width:1180px){

    .v12-studio-layout{
        grid-template-columns:1fr;
    }

    .v12-studio-rail{
        grid-template-columns:1fr;
    }

    .v12-public-service-grid{
        grid-template-columns:repeat(2,minmax(0,1fr));
    }
}
"""

if old_responsive not in css:
    raise SystemExit(
        "ABORT: expected responsive Studio CSS was not found. "
        "No files were changed."
    )

css = css.replace(old_responsive, new_responsive, 1)

old_mobile_last_child = """    .v12-studio-rail .v12-source-card:last-child{
        grid-column:auto;
    }

"""

if old_mobile_last_child not in css:
    raise SystemExit(
        "ABORT: expected mobile rail rule was not found. "
        "No files were changed."
    )

css = css.replace(old_mobile_last_child, "", 1)

# ------------------------------------------------------------
# 6. Atomic writes only after every verification succeeded
# ------------------------------------------------------------

def atomic_write(path: Path, content: str):
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


atomic_write(TEMPLATE, template)
atomic_write(CSS, css)

print("Business OS v12.1 - Studio Correctness Repair")
print("Repository:", ROOT)
print()
print("PASS: readiness now counts backend 'ok' values")
print("PASS: required blockers are shown separately from completeness")
print("PASS: Studio rail collapses earlier and stays single-column")
print("PASS: owner-facing Website Studio copy simplified")
print("PASS: live publishing behavior unchanged")
print("PASS: provider/action behavior unchanged")
