# Business OS v2

This upgrade keeps your existing `.env` and `business_os.db` and migrates the database in place.

## Adds
- Prospect Finder in the web dashboard using Google Places API (New)
- Google Place ID duplicate protection
- Evidence-first Website Auditor
- Estimate marketing language separated from actual estimate forms
- Scheduling language separated from actual booking systems
- Owned-site vs marketplace detection
- Audit confidence, pages checked, and evidence on the prospect detail page
- Opportunity scores that do not award missing-feature points before an audit completes

## Important
Do **not** delete your existing `.env` or `business_os.db`.

## Install / update packages
```powershell
python -m pip install -r requirements.txt
```

## Run
```powershell
python app.py
```
Then open `http://127.0.0.1:5000`.

The auditor analyzes public HTML. JavaScript-only widgets can be missed, so the UI says “Not detected” rather than claiming a feature definitely does not exist.
