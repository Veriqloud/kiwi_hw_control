
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

dispable automatic updates

~~~~.bash
sudo vim /etc/apt/apt.conf.d/20auto-upgrades    # set both lines to "0"
~~~~

to make usb devices user accessible add the following lines to `/etc/udev/rules.d/usb.rules` 

for the RNG 

`SUBSYSTEM=="usb", ATTRS{idVendor}=="1fc9", ATTRS{idProduct}=="8111", MODE="0660", GROUP="vq-user"`

for the APD

`SUBSYSTEM=="usb", ATTRS{idVendor}=="04d8", ATTRS{idProduct}=="f7b1", MODE="0660", GROUP="vq-user"`

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
cd ..
scp check_systemd.sh SSH_ALICE:~/bin/
scp check_systemd.sh SSH_BOB:~/bin/

```

on remote machines

```.bash
sudo rsync --chown root:root *.service  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hw.service
sudo systemctl enable hws.service
sudo systemctl enable mon.service
sudo systemctl enable gc.service
sudo systemctl enable rng.service
check_status.sh     # make sure they are up
```

logfiles are in ~/log/

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




Create the second service decoy_rng similar to the rng.service on Alice when she use decoy state.

```
ExecStart=/home/vq-user/qline/hw_control/rng_fpga/decoy_rng2file
```
Start both service and check status

```
service rng status
service decoy_rng status
```

# First run

```.bash
cd local
hw_alice.py init --rst_tmp
hw_alice.py init --rst_default
hw_bob.py init --rst_tmp
hw_bob.py init --rst_default
```



