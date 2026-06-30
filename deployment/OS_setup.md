
# Installation

install ubuntu-server 22.4

- name: vq-user
- machine: ql001
- username: vq-user
- accept to install openssl
- partition standard with one full partition (no lvm)
- copy .bashrc


Install some packages

~~~~.bash
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get -y install apt-utils build-essential tree python-is-python3 openssl fio neofetch zoxide ipython python3-pip
sudo apt install python3-numpy python3-termcolor python3-tabulate
sudo reboot
python3 -m pip install --upgrade termcolor --break-system-packages
~~~~


Network: we have two network interfaces managed by netplan. Make sure `/etc/netplan/01-somename.yaml` looks something like this:

```
network:
  version: 2
  renderer: networkd
  ethernets:
    eth_client:
      match:
        macaddress: 9c:6b:00:62:82:fc
      dhcp4: true
      optional: true
      set-name: eth_client
    eth_wrs:
      dhcp4: false
      addresses:
        - 192.168.10.12/24
      optional: true
      match:
        macaddress: 9c:6b:00:62:82:fd
      set-name: eth_wrs
```

then update with `sudo netplan apply`. check with `ip ad`.

[Lan power on](https://www.claudiokuenzler.com/blog/1208/how-to-enable-wake-on-lan-wol-asrock-b550-motherboard-linux)

- go to bios -> advanced -> ACPI Configuration -> I219 Lan Power On -> enable
- check networks card: `sudo ethtool enp3s0 | grep Wake` should show `pumbg` and `g`
- on some machine in the netowork: `wakeonlan a8:a1:59:b7:de:fe`

beware: BIOS can reset upon a power cut or failed boot etc. If you notice the wakeonlan does not work any more, recheck the bios settings.

dispable automatic updates

~~~~.bash
sudo vim /etc/apt/apt.conf.d/20auto-upgrades    # set both lines to "0"
~~~~

to make usb devices user accessible add the following lines to `/etc/udev/rules.d/usb.rules` 

for the RNG on Bob 


`SUBSYSTEM=="tty", ATTRS{idVendor}=="1fc9", ATTRS{idProduct}=="8111", MODE="0666", GROUP="vq-user", SYMLINK+="ttyRNG0"`

for the two identical RNGs on Alice, lookup the serail number with `lsusb -v -d 1fc9:8111 | grep iSerial` and do

`SUBSYSTEM=="tty", ATTRS{idVendor}=="1fc9", ATTRS{idProduct}=="8111", ATTRS{serial}=="SERIALNUMBER1", MODE="0666", GROUP="vq-user", SYMLINK+="ttyRNG0"`

`SUBSYSTEM=="tty", ATTRS{idVendor}=="1fc9", ATTRS{idProduct}=="8111", ATTRS{serial}=="SERIALNUMBER2", MODE="0666", GROUP="vq-user", SYMLINK+="ttyRNG1"`

for the APD

`SUBSYSTEM=="usb", ATTRS{idVendor}=="04d8", ATTRS{idProduct}=="f7b1", MODE="0660", GROUP="vq-user", SYMLINK+="usbAPD0"`

fot the LASER

`SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6014", MODE="0666", GROUP="vq-user", SYMLINK+="ttylaser"`


to make xdma user accessible add the following lines to `/etc/udev/rules.d/xdma.rules` 

~~~~
KERNEL=="xdma0_user", MODE="0666"
KERNEL=="xdma0_c2h_0", MODE="0666"
KERNEL=="xdma0_c2h_1", MODE="0666"
KERNEL=="xdma0_c2h_2", MODE="0666"
KERNEL=="xdma0_c2h_3", MODE="0666"
KERNEL=="xdma0_h2c_0", MODE="0666"
KERNEL=="xdma0_h2c_1", MODE="0666"
KERNEL=="xdma0_h2c_2", MODE="0666"
KERNEL=="xdma0_h2c_3", MODE="0666"
~~~~

to make symlink with a fixed name to the usb RNG add the following line to /etc/udev/rules.d/usb.rules

```
SUBSYSTEM=="tty", ATTRS{idVendor}=="1fc9", ATTRS{idProduct}=="8111", SYMLINK+="ttyRNG0", MODE="0666", GROUP="vq-user"
```

and on Bob for the APD:

```
SUBSYSTEM=="usb", ATTRS{idVendor}=="04d8", ATTRS{idProduct}=="f7b1", SYMLINK+="usbAPD0", MODE="0660", GROUP="vq-user"
```

add vq-user to dialout group and reload the rules. Reboot!
```
sudo usermod -aG dialout vq-user
sudo udevadm control --reload
sudo udevadm trigger
```

# Environment

add `PYTHONPATH="/home/vq-user"` to `/etc/environment`

increase histsize in bashrc and add

```
alias ..='cd ..'
export PATH=$PATH:.

eval "$(zoxide init bash)"

```

add the following line to `~/.profile`

```
export PYTHONPATH=/home/vq-user
```

create some folders

```.bash
mkdir log
mkdir hw_control/config
mkdir hw_control/data/tdc
```


# PCIe driver

compile driver and install 

~~~~.bash
git clone https://github.com/Xilinx/dma_ip_drivers.git
cd XDMA/linux-kernel/xdma/
sudo make clean
sudo make install
~~~~

Ubuntu 24.04.02: there is already an xdma module preinstalled that does not work for us. To make sure depmod loads our custom module of the same name, modify the priority file `/etc/depmod.d/ubuntu.conf` in the following way. This will look first in the folder xdma, where our custom module was copied to by the previous command

```
search xdma updates ubuntu built-in
```

generate keys for signing kernel module and sign the module that was just installed

[reference about the key for secure boot](https://askubuntu.com/questions/760671/could-not-load-vboxdrv-after-upgrade-to-ubuntu-16-04-and-i-want-to-keep-secur/768310#768310)

~~~~.bash
sudo openssl req -new -x509 -newkey rsa:2048 -keyout signing_key.pem -outform DER -out signing_key.x509 -nodes -subj "/CN=Owner/"
/usr/src/linux-headers-$(uname -r)/scripts/sign-file sha256 signing_key.pem signing_key.x509 /lib/modules/$(uname -r)/xdma/xdma.ko
~~~~

tell the system to load the drive automatically at boot

```.bash
echo xdma | sudo tee /etc/modules-load.d/xdma.conf
```

register the key to the motherboard

~~~~.bash
sudo mokutil --import signing_key.x509
~~~~

reboot and follow instructions to enroll MOK (machine owner key). Check after reboot that the module was loaded: `lsmod | grep xdma`



# Tranfer files

clone repo `git@github.com:Veriqloud/kiwi_hw_control.git` and probably `git@github.com:Veriqloud/hw_sim.git`

```.bashrc
cd deployment
make    # to build the rust programs
cd ../config/qlineX             # update ips in network.json
gen_config -n network.json -a remote/alice -b remote/bob
deploy all  # make sure all files have been copied
export QLINE_CONFIG_DIR=YOURPATH/kiwi_hw_control/config/qlineX
```

# setup systemctl

on local machine

```.bahsrc
cd deployment/systemd
scp *.service SSH_ALICE:~/
scp *.service SSH_BOB:~/
scp wait-for-boot-node.sh SSH_ALICE:~/    # ExecStartPre helper for node.service
scp wait-for-boot-node.sh SSH_BOB:~/
cd ..
scp check_systemd.sh SSH_ALICE:~/bin/
scp check_systemd.sh SSH_BOB:~/bin/

```

on remote machines (decoy_rng.service is for Alice only)

```.bash
sudo rsync --chown root:root *.service  /etc/systemd/system/
sudo systemctl daemon-reload
chmod +x ~/wait-for-boot-node.sh     # used by node.service ExecStartPre (stays in ~)
sudo systemctl enable hw.service
sudo systemctl enable hws.service
sudo systemctl enable mon.service
sudo systemctl enable gc.service
sudo systemctl enable rng.service
sudo systemctl enable kms.service
sudo systemctl enable node.service
sudo systemctl enable restartd.service
sudo systemctl enable logd.service
sudo systemctl enable webinterface.service
check_status.sh     # make sure they are up
```

Note: `node.service` requires the gc/kms binaries and configs to be in place
(`deploy all` + `gen_config`) before it will start, so enable it after a deploy.

logfiles are in /tmp/log/

adjust wait-online for waiting until the networks are up

```.bash
sudo systemctl edit systemd-networkd-wait-online.service
```

add the lines

```.bash
[Service]
ExecStart=
ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --interface=eth_wrs --interface=eth_client
```





# node start ordering

`node.service` is ordered after `kms.service` and `gc.service` (its local IPC
peers via `/tmp/kms.fifo` and `/tmp/gc_startstop`) and has an
`ExecStartPre=/home/vq-user/wait-for-boot-node.sh`. That helper reads the libp2p
boot node ip:port from `~/config/node.json` and blocks until it is reachable: the
Source node is its own boot node and returns immediately, while the Detector node
waits for the Source. This gives correct cross-host startup (Source `node` comes
up before Detector `node`) on a cold boot of both machines. No extra config — just
ensure `~/wait-for-boot-node.sh` exists and is executable (see systemctl setup).


# remote control + shutdown (restartd)

`restartd.service` is a small TCP supervisor (port `restartd` = 13010 in
network.json) that lets the control host restart services and power the node off
**without ssh**, and **without sudo for restarts**. `restartd.py` is deployed to
`~/server/` by `deploy all` (control). Drive it from `local/`:

```.bash
export QLINE_CONFIG_DIR=YOURPATH/kiwi_hw_control/config/qlineX
python3 restart.py <alice|bob> list                       # service states
python3 restart.py <alice|bob> restart <gc|node|kms|...>   # kill MainPID, systemd respawns
python3 shutdown.py <alice|bob|both> --yes                 # power off (recover with wake.sh)
```

Restarts need no sudo: services run as `User=vq-user` with `Restart=always`, so
restartd kills the (vq-user-owned) MainPID and systemd respawns it. Shutdown DOES
need a one-time per-node sudoers rule:

```.bash
echo 'vq-user ALL=(root) NOPASSWD: /usr/sbin/shutdown' | sudo tee /etc/sudoers.d/vq-user-shutdown
sudo chmod 440 /etc/sudoers.d/vq-user-shutdown
sudo visudo -c
```

To reload restartd after updating `restartd.py`: re-`deploy all` then
`kill $(systemctl show -p MainPID --value restartd.service)` (systemd respawns the
new code). Do **not** `pkill -f restartd.py` — the pattern matches your own ssh
shell and drops the session.


# read logs without ssh (logd)

`logd.service` is the read-only sibling of restartd (port `logd` = 13011 in
network.json): it serves the node log files under `~/log` over TCP so the control
host can list/tail/grep them without ssh. `logd.py` is deployed to `~/server/` by
`deploy all` (control). Drive it from `local/`:

```.bash
export QLINE_CONFIG_DIR=YOURPATH/kiwi_hw_control/config/qlineX
python3 logs.py <alice|bob> list                  # available logs + sizes
python3 logs.py <alice|bob> tail <name> [n]        # last n lines (e.g. tail hws 50)
python3 logs.py <alice|bob> grep <pattern> <name>  # last matching lines
```

It's read-only and confined to `*.log` in `~/log` (no path traversal); output is
capped and `tail` seeks from the end so a multi-GB log stays cheap. To reload after
updating `logd.py`: re-`deploy all` then
`kill $(systemctl show -p MainPID --value logd.service)` (systemd respawns it); do
**not** `pkill -f logd.py` (matches your own ssh shell).


# WRS link history (wrs_logger, cron)

`wrs_logger.py` records White Rabbit (`eth_wrs`) link state to `~/log/wrs.log` so
"did the WRS drop?" is answerable after the fact (nothing else logs carrier/IP over
time). It samples the carrier (`/sys/class/net/eth_wrs/carrier`) and the
`192.168.10.x` IP every 5 s and appends a line on any **state change** plus a 5 min
heartbeat. Runs on **both** nodes; read it over TCP through logd (no ssh):

```.bash
python3 logs.py <alice|bob> tail wrs              # recent state + heartbeats
python3 logs.py <alice|bob> grep CHANGE wrs       # only transitions (a drop = carrier=0 / ip=none)
```

It needs no root, so instead of a systemd unit it is persisted with a **user-cron
`@reboot` entry** (survives power-cycles) guarded by `flock` so only one instance
runs. Deploy and (re)start:

```.bash
# from control host: push the script (no file-push over the TCP servers)
scp -J vq remote/wrs_logger.py vq-user@<node_ip>:~/server/

# on each node (once): install the cron entry and start it now
chmod +x ~/server/wrs_logger.py
( crontab -l 2>/dev/null | grep -vF wrs_logger.py; \
  echo "@reboot /usr/bin/flock -n /tmp/wrs_logger.lock /home/vq-user/server/wrs_logger.py 2>>/home/vq-user/log/wrs.log" ) | crontab -
setsid /usr/bin/flock -n /tmp/wrs_logger.lock ~/server/wrs_logger.py >/dev/null 2>>~/log/wrs.log </dev/null &
```

To reload after editing: re-`scp` then `flock -u` is automatic on process exit, so
just `pkill -f wrs_logger.py` and re-run the `setsid ...` line (the `@reboot` entry
restarts it on the next boot regardless).


# routine bring-up

After the one-time setup above, bring the pair up from the control host with one
command (wake -> wait for boot -> check WRS/PCIe -> wait for services -> recover a
wedged gc -> report QBER + stored key count):

```.bash
export QLINE_CONFIG_DIR=YOURPATH/kiwi_hw_control/config/qline1
cd local
./run_qkd.sh qline1            # add --init to recalibrate, --tune to fix high QBER, --status to only report
```


# First run

```.bash
cd local
hw_alice.py init --rst_tmp
hw_alice.py init --rst_default
hw_bob.py init --rst_tmp
hw_bob.py init --rst_default
```



