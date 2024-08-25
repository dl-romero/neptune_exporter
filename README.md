# Neptune Exporter

### Documentation

Neptune Exporter uses port 5006 as documented on [Prometheus: Default Port Allocations](https://github.com/prometheus/prometheus/wiki/Default-port-allocations)

### Installation

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