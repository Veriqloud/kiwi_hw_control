#!/bin/bash

Alice=KAlice

rsync -v lib/config_lib.py $Alice:~/qline/hw_control/lib/
rsync -v main_Alice.py $Alice:~/qline/hw_control/gmain.py
rsync -v gclient_ctl.py $Alice:~/qline/hw_control/

Bob=KBob

rsync -v lib/config_lib.py lib/SPD_OEM.py lib/Aurea.py lib/OEM.so $Bob:~/qline/hw_control/lib/
rsync -v main_Bob.py $Bob:~/qline/hw_control/gmain.py
rsync -v gserver_ctl.py $Bob:~/qline/hw_control/



