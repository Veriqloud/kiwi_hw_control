Alice and Bob have TCP servers running that listen on certain ports. There are two ways of running the control scripts from your personal computer


1) You are in the local network. 

`hw_alice.py` etc will read the ips and ports from config/network.json and connect on ip:port



2) You are somewhere on the internet and have ssh access to vq (veriqloud.pro.dns-orange.fr) who is in the same local network as Alice and Bob. 

`port_forwarding.sh` will establish port forwarding based on config/network.json and config/ports_for_localhost.json.  

    port_forwarding.sh            start
    port_forwarding.sh --status   supervisor, ssh and listener state
    port_forwarding.sh --stop     stop

It runs detached and stays up on its own: a supervisor rebuilds the tunnel when ssh
exits, and kills ssh when the forwards stop listening. Keepalives drop a connection
whose peer went away after 45 s. Pid file and log live in $XDG_RUNTIME_DIR/qline
(/tmp/qline when that is unset).

Rebuild attempts back off 5, 10, 20 ... up to 300 s, and reset to 5 s once a tunnel
has held for a minute, so an unreachable vq is retried on a widening interval rather
than several times a minute. A fresh ssh gets 20 s before the listener check applies,
since it has to authenticate and bind eleven forwards first.

A tunnel left behind by a dead supervisor holds the local ports and can also hold a
half-open connection to a node, which keeps that node's server blocked on it and
refusing new clients. Starting clears any such tunnel first.

`hw_alice.py --use_localhost` will read the ports from config/ports_for_localhost.json and connect on localhost:someotherport






all ports in config/*.son can be freely chosen by the admin. config/networks.json needs to be copied to the machines upon change.





