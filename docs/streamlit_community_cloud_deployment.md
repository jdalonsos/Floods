# Streamlit Community Cloud Deployment Guide For The France Gaspar vs JRC App

This guide explains how to deploy
[src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py)
to Streamlit Community Cloud from this repository.

Important hosting reality as of **June 5, 2026**:

- Streamlit Community Cloud is free, but apps with no traffic for `12` hours go
  to sleep. Source:
  [Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- Community Cloud resource limits are shared across users and may change, but
  the docs currently describe approximately:
  - CPU: `0.078` to `2` cores
  - memory: `690 MB` to `2.7 GB`
  - storage: up to `50 GB`
  Source:
  [Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- Community Cloud runs on Debian Linux and installs Linux packages from a root
  `packages.txt` file. Source:
  [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)

That means this deployment is much easier than Oracle, but it is **not** a true
`24/7` always-on host.

## 1. What Was Added To This Repository

To make this app fit Community Cloud's deployment rules, this repository now
includes:

- [src/requirements.txt](/D:/M2_MoSEF/DataCollection/src/requirements.txt)
  with a minimal dependency set just for this app

This matters because Community Cloud searches for a dependency file starting in
the entrypoint file's directory, then the repository root. Since the app lives
in `src/`, `src/requirements.txt` takes precedence over the larger root
environment files. Source:
[App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)

This app no longer needs a root `packages.txt` for Streamlit Cloud because the
Cloud build only installs the lightweight Python geospatial stack required to
run the map app itself. The heavier raster-processing dependencies are kept out
of the app startup path.

## 2. Before You Deploy

Make sure the branch you want to deploy is pushed to GitHub and includes:

- `src/gaspar_jrc_france_map_app.py`
- `src/requirements.txt`
- the tracked data files used by the app:
  - `data/raw/adminexpress-cog-simpl-000-2025.gpkg`
  - `data/raw/catnat_gaspar.csv`
  - `data/processed/Gaspar_2015_2024.xlsx`
  - `data/processed/france_lau_insee_documentation/events_fr_insee_long.csv`
  - `data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv`
  - `data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv`

## 3. Create Your Community Cloud Account

1. Go to [share.streamlit.io](https://share.streamlit.io/).
2. Sign in with GitHub.
3. Authorize Streamlit Community Cloud to access your repositories.

If your repository is private, Streamlit's docs note that deployment uses a
GitHub deploy key and requires the additional `repo` OAuth scope. Source:
[Status and limitations](https://docs.streamlit.io/deploy/streamlit-community-cloud/status)

## 4. Create The App

1. In Community Cloud, switch to the workspace that matches the repository
   owner.
2. Click `Create app`.
3. Choose `Yup, I have an app`.
4. Fill in:
   - repository: your GitHub repo
   - branch: the branch that contains the app
   - file path: `src/gaspar_jrc_france_map_app.py`
5. Optional: choose a custom subdomain.

Streamlit's docs say the app file can live in a subdirectory, which is exactly
our setup here. Source:
[File organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)

## 5. Set Advanced Settings

Before you click deploy:

1. Open `Advanced settings`.
2. Set Python version to `3.12`.
3. Leave secrets empty for this app.

Community Cloud defaults to Python `3.12` today, but I still recommend setting
it explicitly so the deployment is deterministic. Source:
[Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## 6. Deploy

Click `Deploy`.

Community Cloud will then:

- clone your repository
- install `src/requirements.txt`
- run the app from the repository root with entrypoint
  `src/gaspar_jrc_france_map_app.py`

## 7. Open The App

If deployment succeeds, your public app URL will look like:

```text
https://your-subdomain.streamlit.app
```

## 8. If The Build Fails

Open the Cloud logs from `Manage app`.

The most likely failure modes for this app are:

- memory/resource limits after startup
- import/runtime issues from the geospatial stack

Community Cloud docs say the logs are the primary place to troubleshoot build
and runtime issues. Source:
[Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)

## 9. If The App Launches But Is Slow

This app is much heavier than a toy Streamlit app because it loads:

- France commune geometry
- JRC commune-event rows
- Gaspar workbook data
- commune reconciliation tables

If it launches but feels heavy:

- use the processed workbook mode instead of raw live transform
- keep department boundaries on only when needed
- increase the commune simplify tolerance a little
- filter by one month or one year instead of a broad custom period

## 10. Known Platform Limits

Community Cloud is still a compromise compared with a dedicated VM:

- the app sleeps after `12` hours without traffic
- the app may hit memory limits on some workloads
- all apps are hosted in the United States according to Streamlit's docs

Sources:

- [Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- [Status and limitations](https://docs.streamlit.io/deploy/streamlit-community-cloud/status)

## 11. Exact Deployment Coordinates To Use

When you create the app, use:

- file path: `src/gaspar_jrc_france_map_app.py`
- Python version: `3.12`

If you want, I can help you choose the exact GitHub branch name and then walk
you through the Community Cloud form field by field.
