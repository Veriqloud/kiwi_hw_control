This code is for getting values remotely from the powermeter PM100. 

# Installation

`git clone https://github.com/Thorlabs/Light_Analysis_Examples.git`

and follow instruction 

test with `python3 main.py`


# Taking data

copy `server.py` to the pc with the powermeter. Modify ip address and run it.

run `client.py`. Verify data with `plot.py`


# Using the data

cp calibration data to `Alice:~/hw_control/config/vca_calib.txt`.

Measure the output power on Alice and edit `Alice:~/hw_control/config/output_power.txt`.

now using `hw_alice.py set --photons` should be accurate.

