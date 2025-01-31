#!/bin/bash

Alice=ql001.home

rsync config_lib.py vq-user@$Alice:~/qline/hw_control
rsync main_Alice.py vq-user@$Alice:~/qline/hw_control/main.py



