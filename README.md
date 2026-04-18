# Neptune Exporter

Neptune Exporter is a Prometheus exporter for Neptune Apex and Neptune Fusion.

[Neptune Systems](https://www.neptunesystems.com/) provides monitoring and automation solutions to the marine aquarium community.

## Notice

- This software is not maintained by Neptune Systems.
- The software and its creator are not endorsed by or affiliated with Neptune Systems.

## What this project does

This exporter makes it possible to:

- scrape local Neptune Apex metrics
- scrape Neptune Fusion metrics
- retain long-term telemetry in Prometheus
- build custom dashboards and alerts in Grafana
- compare multiple Apex systems in one monitoring stack

Neptune Exporter listens on port 5006.

## Features

- FastAPI-based HTTP service
- Prometheus endpoints for Apex and Fusion
- export endpoints for logs and JSON diagnostics
- container-friendly health endpoint at /health
- interactive API docs at /docs

## Requirements

### General

- Linux host or a Docker-capable Linux system
- network access to your local Apex controller for Apex scraping
- internet access to apexfusion.com for Fusion scraping

### Native Linux install

- Python 3.10 or later
- Chromium or Chrome plus a compatible ChromeDriver in PATH for Fusion scraping

### Docker install

The included image installs Chromium and ChromeDriver automatically.

## Sample Grafana dashboard

![Sample Dashboard](https://repository-images.githubusercontent.com/847181458/376aab89-3493-4389-bcc4-e788094aaf67)

---

## Linux installation

### 1. Clone the repository

```bash
git clone https://github.com/dl-romero/neptune_exporter.git
cd neptune_exporter
```

### 2. Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install browser dependencies for Fusion scraping

Example for Debian or Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y chromium chromium-driver
```

Example for Rocky, RHEL, or CentOS:

```bash
sudo dnf install -y chromium chromedriver
```

Package names may vary slightly by distribution.

### 4. Create runtime directories

```bash
mkdir -p logs workspace
```

### 5. Configure the exporter

#### Apex configuration

Edit configuration/apex.yml:

```yaml
apex_auths:
  default:
    username: admin
    password: your_local_apex_password
```

You can define more than one auth profile if you scrape multiple local Apex systems that use different credentials.

#### Fusion configuration

Edit configuration/fusion.yml:

```yaml
fusion:
  apex_systems:
    YOUR_FUSION_APEX_ID:
      username: your_fusion_username
      password: your_fusion_password
```

The Fusion Apex ID is the long device identifier shown in the Fusion URL.

#### Optional metadata configuration

You can also customize the API metadata in configuration/exporter.yml.

### 6. Start the exporter manually

```bash
source .venv/bin/activate
python -m uvicorn neptune_exporter:app --host 0.0.0.0 --port 5006
```

### 7. Verify the service

Open these URLs from your browser or test them with curl:

```bash
curl http://127.0.0.1:5006/health
curl http://127.0.0.1:5006/docs
```

Example direct Apex scrape test:

```bash
curl "http://127.0.0.1:5006/metrics/apex?target=192.168.1.50&auth_module=default"
```

Example direct Fusion scrape test:

```bash
curl "http://127.0.0.1:5006/metrics/fusion?fusion_apex_id=YOUR_FUSION_APEX_ID&data_max_age=300"
```

---

## Linux systemd service setup

If you want the exporter to start automatically on boot:

### 1. Copy the application to a permanent location

```bash
sudo mkdir -p /etc/neptune_exporter
sudo cp -R . /etc/neptune_exporter
sudo chown -R YOUR_USERNAME:YOUR_GROUP /etc/neptune_exporter
```

### 2. Install the service file

```bash
sudo cp neptune_exporter.service /etc/systemd/system/neptune_exporter.service
sudo nano /etc/systemd/system/neptune_exporter.service
```

Replace the User value with your Linux username.

### 3. Enable and start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable neptune_exporter
sudo systemctl start neptune_exporter
sudo systemctl status neptune_exporter
```

### 4. Review logs if needed

```bash
journalctl -u neptune_exporter -f
```

After changing configuration/apex.yml or configuration/fusion.yml, restart the service:

```bash
sudo systemctl restart neptune_exporter
```

---

## Docker usage

The included Docker image is the simplest way to run the exporter in a self-contained environment.

### 1. Build the image

From the repository root:

```bash
docker build -t neptune-exporter .
```

### 2. Prepare host directories

```bash
mkdir -p logs workspace
```

Edit the config files in the local configuration directory before starting the container.

### 3. Run the container

```bash
docker run -d \
  --name neptune-exporter \
  --restart unless-stopped \
  --shm-size=1g \
  -p 5006:5006 \
  -v "$(pwd)/configuration:/app/configuration" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/workspace:/app/workspace" \
  neptune-exporter
```

The shared memory setting helps headless Chromium run more reliably for Fusion scraping.

### 4. Verify the container

```bash
docker ps
docker logs neptune-exporter
curl http://127.0.0.1:5006/health
```

### Optional docker compose example

```yaml
services:
  neptune-exporter:
    build: .
    container_name: neptune-exporter
    restart: unless-stopped
    shm_size: 1gb
    ports:
      - "5006:5006"
    volumes:
      - ./configuration:/app/configuration
      - ./logs:/app/logs
      - ./workspace:/app/workspace
```

Start it with:

```bash
docker compose up -d --build
```

---

## Prometheus configuration

Add the exporter to your Prometheus scrape_configs.

### Apex scrape job

```yaml
- job_name: neptune_apex
  static_configs:
    - targets:
        - 192.168.1.50
        - 192.168.1.13
  metrics_path: /metrics/apex
  params:
    auth_module:
      - default
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: YOUR_EXPORTER_HOST:5006
```

### Fusion scrape job

```yaml
- job_name: neptune_fusion
  static_configs:
    - targets:
        - YOUR_FUSION_APEX_ID
  metrics_path: /metrics/fusion
  params:
    data_max_age:
      - 300
  relabel_configs:
    - source_labels: [__param_target]
      target_label: instance
    - source_labels: [__address__]
      target_label: __param_fusion_apex_id
    - target_label: __address__
      replacement: YOUR_EXPORTER_HOST:5006
```

After updating Prometheus, restart it:

```bash
sudo systemctl restart prometheus
```

---

## Available endpoints

- /health
- /docs
- /metrics/apex
- /metrics/fusion
- /export/logs/
- /export/apex/
- /export/fusion/

---

## Troubleshooting

### Apex scrape returns 400

- confirm the target IP is valid
- confirm the auth_module exists in configuration/apex.yml

### Fusion scrape returns 502

- verify the Fusion username and password
- confirm the Fusion Apex ID is correct
- make sure Chromium and ChromeDriver are installed on native Linux installs
- if running in Docker, review container logs with docker logs neptune-exporter

### Export endpoints say the workspace is locked

Wait a few minutes and retry. The exporter prevents overlapping debug exports.

### Service is running but Prometheus cannot scrape it

- verify port 5006 is open on the host
- confirm Prometheus can reach the exporter host over the network
- test locally with curl against /health and /metrics/apex

---

## Support

Please submit bug reports and feature requests here:

[Neptune Exporter Issues](https://github.com/dl-romero/neptune_exporter/issues/new/choose)

An all-in-one installer that combines Neptune Exporter, Prometheus, and Grafana is also available here:

[Neptune Exporter AIO Installer](https://github.com/dl-romero/neptune_exporter_aio_installer)

