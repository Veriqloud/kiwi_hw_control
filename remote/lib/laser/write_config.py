from koheron_control import Controller

port="/dev/ttylaser"
ctl = Controller(port=port)


config = {
    "ldelay": 1000.0,      # Delay before the laser turns on (ms)
    "lason": 1,            # Enable laser
    "ilaser": 236.0,       # Nominal laser current (mA)
    "ilmax": 400.0,        # Maximum allowed laser current (mA)
    "rtset": 8408,       # Thermistor resistance for 29°C
    "tecon": 1,            # Enable TEC (thermoelectric cooler)
    "pgain": 10.0,         # PID proportional gain for temperature control
    "igain": 0.4,          # PID integral gain for temperature control
    "dgain": 0.0,          # PID derivative gain for temperature control
    "tilim": 0.5,          # TEC current limit (A)
    "vtmin": -1,           # Minimum TEC voltage
    "vtmax": 1,            # Maximum TEC voltage
    "tprot": 1,            # Enable temperature protection
    "vldauto": 1           # Enable automatic adjustment of laser supply voltage
}


for param in config:
    ctl.set(param, config[param])

for param in config:
    print(f"{param.upper()} : {ctl.get(param)}")

user_input = input("Save configuration? (yes/no): ")
if user_input.lower() == "yes":
    print(ctl.set("save"))

