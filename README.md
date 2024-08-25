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