Alice and Bob have TCP servers running that listen on certain ports. There are two ways of running the control scripts from your personal computer


1) You are in the local network. 

`hw_alice.py` etc will read the ips and ports from config/network.json and connect on ip:port



2) You are somewhere on the internet and have ssh access to vq (veriqloud.pro.dns-orange.fr) who is in the same local network as Alice and Bob. 

`port_forwarding.sh` will establish port forwarding based on config/network.json and config/ports_for_localhost.json.  

`hw_alice.py --use_localhost` will read the ports from config/ports_for_localhost.json and connect on localhost:someotherport






all ports in config/*.son can be freely chosen by the admin. config/networks.json needs to be copied to the machines upon change.





