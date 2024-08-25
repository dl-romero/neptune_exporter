# Neptune Exporter

### Documentation

Neptune Exporter uses port 5006 as documented on [Prometheus: Default Port Allocations](https://github.com/prometheus/prometheus/wiki/Default-port-allocations).

This repository contains only the Neptune Exporter.<BR>
An all in one (Neptune Exporter, Prometheus and Grafana) installer is available at [Neptune Exporter AIO Installer](https://github.com/dl-romero/neptune_exporter_aio_installer).

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
<BR>

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
After updating these files run the service should be restarted
```
sudo systemctl restart neptune_exporter
```
<BR>

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
After updating these files run the service should be restarted
```
sudo systemctl restart neptune_exporter
```
<BR>
### Prometheus Configuration
File Location: etc/promethues/prometheus.yml<BR>
This should be added to your "scrape_configs":
Example:
```
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
After updating these files run the service should be restarted
```
sudo systemctl restart neptune_exporter
```
<BR>