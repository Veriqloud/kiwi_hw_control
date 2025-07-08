example folder structure:

```
qline2
├── network.json                # source for the network configuration
├── ports_for_localhost.json    # for connection through the internet
└── remote                      
    ├── alice                   # files to be copied over to alice:~/qline/config/
    │   ├── gc_alice.json
    │   └── qber_alice.json
    └── bob                     # files to be copied over to bob:~/qline/config/
        ├── gc_bob.json
        └── qber_bob.json
```

to generate the remote files from network.json, run `gen_config` with the appropriate arguments. 

Example (assuming `gen_config` is globally known):

```.bash
cd qline2
gen_config -n network.json -a remote/alice -b remote/bob
```


For the simulator

```.bash
cd sim
gen_config -n network.json -a alice -b bob -s hw_sim.json
```


