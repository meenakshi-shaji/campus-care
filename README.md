# CampusCare — Campus Safety Response System

A local, demonstration-only campus reporting and response coordination MVP. Built with Flask, SQLite, HTML, CSS, and vanilla JavaScript.

## Run locally

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5001. The SQLite database is created automatically as `campuscare.db` on first run. No API key or external service is needed. Google Fonts are an optional presentation enhancement; the interface falls back to system fonts offline.

## Demo flow

1. At `/login`, switch between the **Reporter** and **Responder** demo portals.
2. Continue as a reporter and submit an issue; save its `CC-YYYY-NNNN` reference.
3. Use **Switch portal** to enter the responder dashboard and review the report.
4. Acknowledge, assign, update, and resolve it; changes appear on the student timeline.

Portal selection is a local demo role switch, not identity verification or production authentication.

Responder actions are simulated. This prototype does not contact real campus responders or emergency services and cannot guarantee assistance. For immediate danger, contact local emergency services or campus security directly.
