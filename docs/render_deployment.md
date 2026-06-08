# Render Deployment Guide For The France Gaspar vs JRC App

This guide explains how to deploy
[src/gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py)
to Render as a Python web service.

Important hosting reality as of **June 5, 2026**:

- Render can deploy directly from a GitHub repository, including private
  repositories connected to your Render account. Source:
  [Deploy from a Git repository](https://render.com/docs/deploy-from-a-git-repository)
- Render web services support WebSockets. Source:
  [Web Services](https://render.com/docs/web-services)
- Free web services spin down after `15` minutes with no inbound traffic and
  then restart on the next request. Source:
  [Free instances](https://render.com/docs/free#free-web-services)

That means Render can give you a different public domain, but it is still **not
true 24/7 free hosting**.

## 1. What Was Added To The Repository

This repository now includes:

- [render.yaml](/D:/M2_MoSEF/DataCollection/render.yaml)
- [.python-version](/D:/M2_MoSEF/DataCollection/.python-version)

These files tell Render:

- which branch to use
- which app to run
- how to install dependencies
- which health endpoint to probe
- which Python major/minor version to use

## 2. Recommended Render Path

Use a **Web Service**, not a static site.

This app is a live Streamlit server and needs:

- Python execution
- an HTTP port
- long-lived app process behavior

## 3. Fastest Manual Setup In The Render Dashboard

1. Go to [dashboard.render.com](https://dashboard.render.com/).
2. Click `New +`.
3. Choose `Web Service`.
4. Connect GitHub if Render asks.
5. Select the repository `jdalonsos/Floods`.

If the branch picker does not show your branch immediately, refresh once or
wait a minute for Git sync.

Then use:

- Branch: `codex-geodata-clean-push`
- Root directory: leave empty
- Runtime: `Python 3`
- Build command: `pip install -r src/requirements.txt`
- Start command:

```bash
python -m streamlit run src/gaspar_jrc_france_map_app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --browser.gatherUsageStats=false
```

- Instance type: `Free`

## 4. Blueprint Alternative

Because the repo includes [render.yaml](/D:/M2_MoSEF/DataCollection/render.yaml),
you can also use:

1. `New +`
2. `Blueprint`
3. select the same repository

Render should detect the blueprint and prefill the web service settings.

## 5. Python Version

The repository includes [.python-version](/D:/M2_MoSEF/DataCollection/.python-version)
set to `3.12` so Render does not default to a newer Python line unexpectedly.

## 6. Health Check

The configured health path is:

```text
/_stcore/health
```

That matches Streamlit's internal health endpoint.

## 7. Expected Public URL

If deployment succeeds, Render gives you a public domain like:

```text
https://gaspar-jrc-france-map.onrender.com
```

The exact subdomain depends on what Render allows in your account.

## 8. Realistic Risk For This App

This app is heavier than a small hello-world Streamlit app because it loads:

- commune geometry
- JRC France event rows
- Gaspar workbook data
- France lookup tables

So even if Render Free deploys successfully, it may still:

- wake up slowly after sleeping
- feel slower than Streamlit Community Cloud
- fail at runtime if the free instance resources are too tight

If that happens, the next step is usually to keep the same setup and just move
to a paid Render instance type.

## 9. Troubleshooting

If the build fails:

- open the service logs in Render
- look for the first Python package error, not only the final summary line

If the service builds but stays unhealthy:

- check whether the logs show Streamlit binding to the wrong port
- confirm the start command still uses `$PORT`
- check whether the process was killed during startup

## 10. What I Recommend You Try First

1. Use manual `Web Service` creation.
2. Keep the commands exactly as written above.
3. Deploy on the `Free` instance first.
4. If the service repeatedly crashes after startup, the likely issue is memory,
   not the deployment syntax.
