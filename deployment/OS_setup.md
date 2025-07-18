
# Installation

install ubuntu-server 22.4

- name: vq-user
- machine: ql001
- username: vq-user
- accept to install openssl
- partition standard with one full partition (no lvm)
- copy .bashrc

don't wait for second network on boot: add `optional: true` to `/etc/netplan/01-netcfg.yaml` to skip waiting at boot if no network is connected. 

Alternativeley

~~~~.bash
sudo systemctl disable systemd-networkd-wait-online.service
sudo systemctl mask systemd-networkd-wait-online.service
~~~~

Install some packages

~~~~.bash
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get -y install apt-utils build-essential tree python-is-python3 python3-pip openssl fio
pip install numpy matplotlib ipython
pip install termcolor
sudo apt-get -y install neofetch
sudo reboot
~~~~

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

add vq-user to dialout group and reload the rules. Reboot!
```
sudo usermod -aG dialout vq-user
sudo udevadm control --reload
sudo udevadm trigger
```

# PCIe driver

[reference about the key for secure boot](https://askubuntu.com/questions/760671/could-not-load-vboxdrv-after-upgrade-to-ubuntu-16-04-and-i-want-to-keep-secur/768310#768310)

generate keys for signing kernel module

~~~~.bash
mkdir ~/driver_certs
cd ~/driver_certs
sudo openssl req -new -x509 -newkey rsa:2048 -keyout signing_key.pem -outform DER -out signing_key.x509 -nodes -subj "/CN=Owner/"
~~~~

compile driver

~~~~.bash
git clone https://github.com/Xilinx/dma_ip_drivers.git
cd XDMA/linux-kernel/xdma/
sudo make install
~~~~

sign module

~~~~.bash
cd ~/driver_certs
/usr/src/linux-headers-MOSTRECENT-generic/scripts/sign-file sha256 signing_key.pem signing_key.x509 XDMAFOLDER/xdma.ko
~~~~

register the key to the motherboard

~~~~.bash
sudo mokutil --import signing_key.x509
~~~~

reboot and follow instructions to enroll MOK (machine owner key)

go to `$xdma/tools` and perform some tests. Change device id in `load_driver.sh` to `9034` or similar (check `lspci`) and location of the driver to `XDMAFOLDER/xdma.ko` in line 73.

~~~~.bash
sudo ./load_driver.sh
sudo ./run_test.sh
sudo ./perform_hwcount.sh 1 1
~~~~

for automatic loading at boot

~~~~.bash
sudo cp path_to/xdma.ko /lib/modules/kernel_version/xdma/xdma.ko
sudo depmod
sudo reboot
~~~~

# RNG Service
Create a system service to run RNG in the background

~~~~.bash
cd /etc/systemd/system
sudo vi rng.service
~~~~
Add following content to rng.service

```
[Unit]                                                                                                           
Description=SwiftRNG Service                                                                                     

[Service]                                                                                                         
ExecStart=/home/vq-user/qline/rng_fpga/rng2fpga                                                       
Restart=always                                                                                                    
User=vq-user                                                                                                      
WorkingDirectory=/home/vq-user/qline/rng_fpga                                                                  
StandardOutput=file:/home/vq-user/qline/log/rng.log                                                                                           
StandardError=file:/home/vq-user/qline/log/rng.log                                                                                           

[Install]                                                                                                         
WantedBy=multi-user.target  
```
Reload 

~~~~.bash
sudo systemctl daemon-reload
~~~~

You can start and stop rng.service manually when device need true RNG

~~~~.bash
sudo systemctl start rng.service
sudo systemctl stop rng.service
~~~~

Create the second service decoy_rng similar to the rng.service on Alice when she use decoy state.

```
ExecStart=/home/vq-user/qline/hw_control/rng_fpga/decoy_rng2file
```
Start both service and check status

```
service rng status
service decoy_rng status
```

# systemctl setup

add `PYTHONPATH=/home/vq-user` to `/etc/environment`

copy files from `systemd` to machine:~/

and then on remote machine

```.bash
cd 
sudo rsync --chown root:root *.service  /etc/systemd/system/
rm *.service
sudo systemctl enable hw.service
sudo systemctl enable hws.service
sudo systemctl enable mon.service
sudo systemctl enable gc.service
```



