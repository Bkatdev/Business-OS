# Business OS

A local Flask prototype for ranking service-business prospects, reviewing digital gaps,
tracking pipeline status, storing notes, and preparing for future AI-agent workflows.

## Run

```powershell
python app.py
```

Then open:

http://127.0.0.1:5000

The app creates `business_os.db` automatically on first run.

## Current v1 features

- Dashboard
- Persistent SQLite prospect database
- Add prospect
- CSV import/export
- Search and filters
- Opportunity scoring
- Prospect detail pages
- Pipeline status updates
- Persistent notes
- Audit overview
- Agent center with truthful connection status
- Approval queue
- Client view
- Responsive UI

## Important

The current Website Auditor uses stored business fields and scoring rules.
It does not yet inspect live websites automatically.

The Agent Center is architecture/UI only unless explicitly marked otherwise.
