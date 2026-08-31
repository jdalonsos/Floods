# Oracle Cloud Always Free Deployment Guide For The France Gaspar vs JRC Streamlit App

This guide prepares a real `24/7` deployment package for
[gaspar_jrc_france_map_app.py](/D:/M2_MoSEF/DataCollection/src/gaspar_jrc_france_map_app.py)
on an Oracle Cloud Always Free VM.

Important hosting reality as of **June 4, 2026**:

- Streamlit Community Cloud is free, but free apps go to sleep after `12` hours
  without traffic and have limited resources. Source:
  [Streamlit docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)
- Hugging Face Spaces on free hardware also go to sleep when unused; their docs
  say to run indefinitely you should upgrade to paid hardware. Source:
  [Hugging Face docs](https://huggingface.co/docs/hub/spaces-overview)
- Render free web services spin down after `15` minutes idle. Source:
  [Render free docs](https://render.com/docs/free)
- Oracle documents an **Always Free** VM tier that can be used to run
  small-scale applications for the life of the account in the home region.
  Source:
  [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

That is why this package targets Oracle Always Free instead of Streamlit Cloud.

## 1. What This Package Deploys

The deployment package lives in:

- [deploy/oracle_always_free](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free)

It deploys:

- the Streamlit app itself
- the minimum source files required by the app
- the minimum France data files required by the app
- Docker restart behavior so the service comes back after VM reboot
- an optional HTTPS reverse proxy using Caddy

The container image includes only the data needed by this app:

- `data/raw/adminexpress-cog-simpl-000-2025.gpkg`
- `data/raw/catnat_gaspar.csv`
- `data/processed/Gaspar_2015_2024.xlsx`
- `data/processed/france_lau_insee_documentation/events_fr_insee_long.csv`
- `data/processed/france_lau_insee_documentation/fr_lau_insee_lookup.csv`
- `data/processed/france_lau_insee_documentation/fr_old_insee_to_current_update_ready.csv`

## 2. Recommended Oracle VM Shape

Recommended:

- image: `Ubuntu 24.04`
- shape: `VM.Standard.A1.Flex`
- OCPU: `4`
- memory: `24 GB`

Why:

- this app loads `geopandas`, `rasterio`, and several geospatial files
- the current app data includes a commune geometry file around `55 MB` and a
  JRC France event table around `41 MB`
- the smaller x86 Always Free micro instances are much more likely to feel too
  constrained for a responsive map app

Oracle notes that Always Free capacity can be temporarily unavailable in some
regions or availability domains. If that happens, try another availability
domain or reduce the requested size. Source:
[Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

## 3. Network Rules You Need In OCI

Before SSH or app access works, open the ports in your Oracle VCN security list
or NSG.

Minimum rules:

- `22/tcp` for SSH
- `8501/tcp` if you want to expose Streamlit directly

Optional rules for HTTPS mode:

- `80/tcp`
- `443/tcp`

If you use HTTPS mode with Caddy, you can keep `8501` closed publicly and
expose only `80` and `443`.

## 4. SSH Into The VM

After the VM is created:

```bash
ssh -i /path/to/your_oracle_private_key ubuntu@YOUR_VM_PUBLIC_IP
```

## 5. Clone The Repository On The VM

On the VM:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/jdalonsos/Floods.git
cd Floods
git checkout codex-geodata-clean-push
```

If you prefer SSH:

```bash
sudo apt update
sudo apt install -y git
git clone git@github.com:jdalonsos/Floods.git
cd Floods
git checkout codex-geodata-clean-push
```

## 6. Install Docker And Open The VM Firewall

For direct public Streamlit access on `8501`:

```bash
sudo bash deploy/oracle_always_free/bootstrap_ubuntu.sh direct
```

For reverse-proxied `80/443` mode:

```bash
sudo bash deploy/oracle_always_free/bootstrap_ubuntu.sh caddy
```

Then log out and back in so your user picks up the Docker group membership.

## 7. Direct Deployment Mode

This is the simplest mode. The app is public at:

```text
http://YOUR_VM_PUBLIC_IP:8501
```

Deploy it with:

```bash
cd deploy/oracle_always_free
cp .env.example .env
docker compose -f compose.yaml build --pull
docker compose -f compose.yaml up -d
docker compose -f compose.yaml ps
```

Or simply:

```bash
bash deploy_on_vm.sh direct
```

Default port mapping:

- host `8501` -> container `8501`

You can change the host port in `.env`:

```dotenv
HOST_PORT=8501
```

## 8. Optional HTTPS Deployment With Caddy

If you have a domain name, point an `A` record to your VM public IP.

Edit [deploy/oracle_always_free/.env.example](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/.env.example)
into `.env` and set:

```dotenv
HOST_PORT=8501
APP_DOMAIN=your-domain.example
LE_EMAIL=you@example.com
```

Then deploy:

```bash
cd deploy/oracle_always_free
docker compose -f compose.yaml -f compose.caddy.yaml build --pull
docker compose -f compose.yaml -f compose.caddy.yaml up -d
docker compose -f compose.yaml -f compose.caddy.yaml ps
```

Or use:

```bash
bash deploy_on_vm.sh caddy
```

With this mode:

- Caddy terminates HTTPS
- Caddy proxies traffic to the internal Streamlit container
- Docker restart rules keep both services up after reboot

## 9. Verify The App

Direct mode:

```bash
curl http://127.0.0.1:8501/_stcore/health
```

If you are using HTTPS mode:

```bash
curl http://127.0.0.1:80
curl https://YOUR_DOMAIN
```

Container logs:

```bash
cd deploy/oracle_always_free
docker compose logs -f app
```

With HTTPS mode:

```bash
docker compose -f compose.yaml -f compose.caddy.yaml logs -f
```

## 10. Update The App Later

From the repository root on the VM:

```bash
cd ~/Floods/deploy/oracle_always_free
bash update_on_vm.sh direct
```

Or for HTTPS mode:

```bash
cd ~/Floods/deploy/oracle_always_free
bash update_on_vm.sh caddy
```

If you prefer executable scripts, run this once after cloning:

```bash
chmod +x deploy/oracle_always_free/*.sh
```

This script:

- pulls the latest Git commits
- rebuilds the image
- restarts the app with the new code

## 11. Why This Should Stay Up 24/7

This package is meant for a real VM, not a hobby sleep-based platform.

The app stays available because:

- the Oracle VM itself can remain running continuously
- the container uses `restart: unless-stopped`
- Docker is enabled at boot by `bootstrap_ubuntu.sh`

That means after a VM reboot:

- Docker starts automatically
- the app container is started again automatically

Important Oracle caveat:

- Oracle documents that **idle Always Free compute instances may be reclaimed**
  if CPU, network, and memory utilization all remain below Oracle's thresholds
  during a `7-day` period. Source:
  [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

So this is the closest realistic **free always-on VM** option for this app, but
it is still not the same thing as a paid uptime guarantee or SLA.

## 12. Troubleshooting

### The VM was created but the app is unreachable

Check:

- OCI ingress rules
- Ubuntu `ufw` rules
- `docker compose ps`
- `docker compose logs -f app`

### The app starts but crashes during import

Check:

- `docker compose logs -f app`
- whether the build finished fully
- whether the VM has enough RAM

### Oracle says there is no capacity for Always Free

Oracle documents that Always Free capacity may be temporarily unavailable for a
shape in a given availability domain. Try:

- another availability domain
- another home region if you are still early in setup
- a smaller A1 allocation such as `2 OCPU / 12 GB`

### The app is too slow on first load

That is expected more than on a lightweight Streamlit toy app because this app
loads:

- commune geometry
- France lookup tables
- JRC event rows
- GASPAR workbook data

After the first run, Streamlit caching helps subsequent interactions.

## 13. Files Created For This Deployment

Package files:

- [deploy/oracle_always_free/Dockerfile](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/Dockerfile)
- [deploy/oracle_always_free/runtime-requirements.txt](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/runtime-requirements.txt)
- [deploy/oracle_always_free/compose.yaml](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/compose.yaml)
- [deploy/oracle_always_free/compose.caddy.yaml](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/compose.caddy.yaml)
- [deploy/oracle_always_free/Caddyfile](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/Caddyfile)
- [deploy/oracle_always_free/.env.example](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/.env.example)
- [deploy/oracle_always_free/bootstrap_ubuntu.sh](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/bootstrap_ubuntu.sh)
- [deploy/oracle_always_free/deploy_on_vm.sh](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/deploy_on_vm.sh)
- [deploy/oracle_always_free/update_on_vm.sh](/D:/M2_MoSEF/DataCollection/deploy/oracle_always_free/update_on_vm.sh)

## 14. What I Did Not Do

I did not actually create an Oracle VM or deploy this app to your Oracle
account, because that requires your OCI credentials, tenancy configuration,
network choices, and domain setup if you want HTTPS.

What is ready now is the deployment package itself, so once you have an Oracle
Always Free VM, you can use these files directly.
