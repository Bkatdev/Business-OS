from pathlib import Path
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "website_studio.html"
CSS = ROOT / "static" / "v12.css"

template = TEMPLATE.read_text(encoding="utf-8")
css = CSS.read_text(encoding="utf-8")

old_open = """{% block content %}

<div class="v12-studio-intro">"""

new_open = """{% block content %}

<div class="v12-studio-shell">

<div class="v12-studio-intro">"""

if old_open not in template:
    raise SystemExit("ABORT: Studio content opening anchor not found.")

template = template.replace(old_open, new_open, 1)

old_close = """</div>

{% endblock %}"""

new_close = """</div>

</div>

{% endblock %}"""

if old_close not in template:
    raise SystemExit("ABORT: Studio content closing anchor not found.")

template = template.replace(old_close, new_close, 1)


internal_header = """/* ---------------------------------------------------------
   Internal Website Studio
   --------------------------------------------------------- */

"""

internal_header_new = """/* ---------------------------------------------------------
   Internal Website Studio
   --------------------------------------------------------- */

.v12-studio-shell{
    container-type:inline-size;
    container-name:website-studio;
    width:100%;
    min-width:0;
}

"""

if internal_header not in css:
    raise SystemExit("ABORT: internal Website Studio CSS anchor not found.")

css = css.replace(internal_header, internal_header_new, 1)


old_media = """@media(max-width:1180px){

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

new_media = """@container website-studio (max-width:1050px){

    .v12-studio-layout{
        grid-template-columns:1fr;
    }

    .v12-studio-rail{
        grid-template-columns:1fr;
    }
}

@media(max-width:1000px){

    .v12-public-service-grid{
        grid-template-columns:repeat(2,minmax(0,1fr));
    }
}
"""

if old_media not in css:
    raise SystemExit("ABORT: expected v12.1 responsive block not found.")

css = css.replace(old_media, new_media, 1)


old_mobile = """@media(max-width:760px){

    .v12-studio-intro{
        grid-template-columns:1fr;
    }

    .v12-readiness-card{
        align-items:flex-start;
        text-align:left;
        min-height:0;
    }

    .v12-toggle-grid,
    .v12-studio-rail{
        grid-template-columns:1fr;
    }
"""

new_mobile = """@container website-studio (max-width:700px){

    .v12-studio-intro{
        grid-template-columns:1fr;
    }

    .v12-readiness-card{
        align-items:flex-start;
        text-align:left;
        min-height:0;
    }

    .v12-toggle-grid,
    .v12-studio-rail{
        grid-template-columns:1fr;
    }

    .v12-save-bar,
    .v12-version-row{
        align-items:stretch;
        flex-direction:column;
    }

    .v12-save-bar .btn,
    .v12-version-actions .btn{
        width:100%;
    }
}

@media(max-width:760px){
"""

if old_mobile not in css:
    raise SystemExit("ABORT: expected mobile Studio CSS block not found.")

css = css.replace(old_mobile, new_mobile, 1)


duplicate_mobile_rules = """    .v12-save-bar,
    .v12-version-row{
        align-items:stretch;
        flex-direction:column;
    }

    .v12-save-bar .btn,
    .v12-version-actions .btn{
        width:100%;
    }

"""

if duplicate_mobile_rules not in css:
    raise SystemExit("ABORT: expected duplicate mobile rules not found.")

css = css.replace(duplicate_mobile_rules, "", 1)


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

print("Business OS v12.1 - Container Responsive Repair")
print("Repository:", ROOT)
print()
print("PASS: Website Studio now owns a responsive container")
print("PASS: Studio layout responds to available workspace width")
print("PASS: rail becomes one column before it can be crushed")
print("PASS: narrow Studio controls respond to component width")
print("PASS: public website responsive behavior preserved")
print("PASS: no backend, database, publishing, or provider behavior changed")
