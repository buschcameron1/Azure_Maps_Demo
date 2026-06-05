# AzMaps MVP Demo

This repo is a small MVP that:

- Pulls employee addresses from Microsoft Graph (`/users`)
- Loads office locations from `offices.json`
- Finds the nearest office for a selected employee
- Shows a driving route on an Azure Map

## Stack

- Backend: Flask (`main.py`)
- Frontend: vanilla JavaScript + HTML/CSS (`templates/index.html`, `static/app.js`, `static/style.css`)
- APIs: Microsoft Graph + Azure Maps (Search + Route)

## Important: Not Production Ready

This project is intentionally demo/MVP quality and is **not** production-ready.

Known security concern:

- The Azure Maps subscription key is exposed in browser-visible client code/markup.
- This is acceptable for a quick demo, but **not** acceptable for production.

## Prerequisites

1. Python installed
2. Required Python packages installed
3. Interactive Azure login completed before running server:

```powershell
az logout
az login
```

To ensure a clean authentication session, always logout first, then login. The app uses `DefaultAzureCredential` for Graph calls, so an active Azure login is required.

## Run the Server

From the repo root:

```powershell
py .\main.py run
```

Then open:

- `http://127.0.0.1:5000`

## Notes

- Office data is read from `offices.json` (Places-like shape)
- Employee data is fetched from Graph on demand and cached in memory
- Routing uses Azure Maps Route API (driving route geometry)
