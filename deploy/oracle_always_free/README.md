# Oracle Cloud Always Free deployment package

This folder contains a deployable package for hosting
`src/gaspar_jrc_france_map_app.py` on an Oracle Cloud Always Free VM.

Recommended target:

- shape: `VM.Standard.A1.Flex`
- OS: `Ubuntu 24.04`
- architecture: `Arm64`
- sizing: `4 OCPU / 24 GB RAM` if your region has capacity

Why this target:

- it is the most realistic Always Free option for a geospatial Streamlit app
- it offers much more memory than the tiny x86 micro instances
- the container restarts automatically after VM reboot through Docker's
  `restart: unless-stopped`
- Oracle still documents that idle Always Free compute instances may be
  reclaimed, so this is the strongest free option here, not a formal uptime SLA

Files in this package:

- `Dockerfile`: builds the runtime image with only the app-specific data and code
- `runtime-requirements.txt`: slim Python dependency set for this app
- `compose.yaml`: direct public deployment on port `8501`
- `compose.caddy.yaml`: optional reverse proxy with automatic HTTPS
- `Caddyfile`: reverse proxy configuration
- `.env.example`: editable runtime settings
- `bootstrap_ubuntu.sh`: installs Docker and opens firewall ports
- `deploy_on_vm.sh`: builds and starts the app
- `update_on_vm.sh`: pulls updates and rebuilds the app

The full step-by-step guide is in:

- `docs/oracle_always_free_streamlit_deployment.md`
