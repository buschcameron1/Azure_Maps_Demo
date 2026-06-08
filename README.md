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
2. Azure Maps account created (https://learn.microsoft.com/en-us/azure/azure-maps/quick-demo-map-app#create-an-azure-maps-account)
3. config_template.json renamed to config.json with key added
4. Required Python packages installed

```powershell
py -m pip install -r requirements.txt
```

5. Interactive Azure login completed before running server:

```powershell
az logout
az login
```

To ensure a clean authentication session, always logout first, then login. The app uses `DefaultAzureCredential` for Graph calls, so an active Azure login is required.

## Run the Python SDK Demo (gathers nearest office for all employees)

From the repo root:

```powershell
py .\main.py
```

## Run the Server/Web App

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
