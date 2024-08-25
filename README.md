# Neptune Exporter

### Documentation

Neptune Exporter uses port 5006 as documented on [Prometheus: Default Port Allocations](https://github.com/prometheus/prometheus/wiki/Default-port-allocations)

### Installation
```
pip3 install -r requirements.txt
sudo mkdir /etc/neptune_exporter
sudo cp -R apps/neptune_exporter/* /etc/neptune_exporter
sudo cp apps/neptune_exporter/neptune_exporter.service /etc/systemd/system
sudo chown <USERNAME>:<USERGROUP> -R /etc/neptune_exporter # Replace <USERNAME>,<USERGROUP> with your actual username and group.
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