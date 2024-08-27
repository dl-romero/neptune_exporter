# Neptune Exporter
A Prometheus Exporter for the Neptune Apex and Neptune Fusion.<br>
[Neptune Systems](https://www.neptunesystems.com/) provides monitoring and automation solutions to the Marine Aquarists Community.<br>

Notice: 
  - This software is not maintaintained by Neptune Systems.
  - The software and its creator(s) are not endorsed or affiliated with Neptune Systems in anyway shape or form.

The purpose of this exporter is to:
 - Enable Neptune users with the capability of creating alternative dashboards and alerting.
 - Provide the ability to retain data long term.
 - Provide Multi-Apex-Unit users the ability to compare data between Apex Units.
 - Enable the capability to create multi-vendor dashbaords.

### Documentation

Neptune Exporter uses port 5006 as documented on [Prometheus: Default Port Allocations](https://github.com/prometheus/prometheus/wiki/Default-port-allocations).<BR>
<BR>
Please submit bug reports and feature requests [HERE](https://github.com/dl-romero/neptune_exporter/issues/new/choose) or by clicking the Issues tab in this repository.

This repository contains only the Neptune Exporter.<BR>
An all in one (Neptune Exporter, Prometheus and Grafana) installer is available at [Neptune Exporter AIO Installer](https://github.com/dl-romero/neptune_exporter_aio_installer).

### Requirements
 - Linux OS.
    - Confirmed working OS:
      - Rocky 9
      - CentOS 7
 - Python 3.9.X
    - Python Packages:
      - fastapi v0.112.1
      - PyYAML v6.0.2
      - Requests v2.32.3
      - selenium v4.23.1
      - uvicorn v0.30.6

### Download and Installation Instructions
The below instructions do not include the setup of the required fusion.yml and apex.yml files.<BR>
See Fusion Configurations and Apex Configuration.
```
wget https://github.com/dl-romero/neptune_exporter/archive/refs/heads/main.zip
cd neptune_exporter-main
pip3 install -r requirements.txt
sudo mkdir /etc/neptune_exporter
sudo cp -R * /etc/neptune_exporter
sudo cp neptune_exporter.service /etc/systemd/system
# In the command below. Replace <USERNAME>,<USERGROUP> with your actual username and group.
sudo chown <USERNAME>:<USERGROUP> -R /etc/neptune_exporter 
sudo vi /etc/systemd/system/neptune_exporter.service 
# Replace <USERNAME> with your actual username.
# Press Esc key.
# Enter a colon ":" without the quotes.
# Enter "wq!" without the quotes.
# Press Enter key.
sudo systemctl daemon-reload
sudo systemctl start neptune_exporter
sudo systemctl enable neptune_exporter
sudo systemctl status neptune_exporter
```

### Fusion Configuration
File Location: configuration/fusion.yml<BR>
Example:
```
fusion:
  apex_systems:
    234j5nliu2345oin2345in2345: # <- Apex ID from URL.
      username: reef_master # <- Fusion Login Username
      password: i-glue-animals-to-rocks #<- Fusion Login Password 
```
After updating this file the service should be restarted
```
sudo systemctl restart neptune_exporter
```

### Apex Configuration
File Location: configuration/apex.yml<BR>
Example:
```
apex_auths:
  'default':
    username: 'admin'
    password: '1234'
  'new_auth_name': # <- Call this whatever you want just no duplicates. prometheus.yml will this.
    username: 'admin' # <- Apex (local) Login Username
    password: 'i-glue-animals-to-rocks' #<- Apex (local) Login Password 
```
After updating this file the service should be restarted
```
sudo systemctl restart neptune_exporter
```

### Prometheus Configuration
File Location: etc/promethues/prometheus.yml<BR>
This should be added to your "scrape_configs":
Example:
```
scrape_configs:
- job_name: neptune_apex
  static_configs:
  - targets: 
    - 192.168.1.50 # <- Apex System 1
    - 192.168.1.13 # <- Apex System 2
    - 192.168.1.8 # <- Apex System 3
  metrics_path: /metrics/apex
  params:
    auth_module:
    - default # <- This is the name of the apex_auth you added in the apex.yml file.
  relabel_configs:
  - source_labels:
    - __address__
    target_label: __param_target
  - source_labels:
    - __param_target
    target_label: instance
  - target_label: __address__
    replacement: <YOUR NEPTUNE EXPORTERS HOSTNAME HERE>:5006 # <- Replace with your hostname where the Neptune Exporter is hosted.
    
- job_name: neptune_fusion
  static_configs:
  - targets: 
     - 234j5nliu2345oin2345in2345 # <- These are the Apex IDs you added in the fusion.yml file.
     - j24j5nliasdfasdfaa45fdsdf1 # <- These are the Apex IDs you added in the fusion.yml file.
  metrics_path: /metrics/fusion
  params:
    data_max_age:
    - 300 # <- This should be the same as your scrape_interval set at the top of this file.
  relabel_configs:
  - source_labels:
    - __param_target
    target_label: instance
  - source_labels:
    - __address__
    target_label: __param_fusion_apex_id
  - target_label: __address__
    replacement: <YOUR NEPTUNE EXPORTERS HOSTNAME HERE>:5006 # <- Replace with your hostname where the Neptune Exporter is hosted.
```
After updating this file the service should be restarted
```
sudo systemctl restart prometheus
```
<BR>