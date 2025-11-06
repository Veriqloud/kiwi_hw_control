from koheron_control import Controller

# Connect to the CTL300E controller
port = "/dev/ttylaser"
ctl = Controller(port=port)

# List of parameters to read for laser and temperature status
status_params = [
    "ilmon",   # Monitored laser current (mA)
    "rtact",   # Thermistor actual resistance (Ω)
    "itec",    # TEC current (A)
    "vtec",    # TEC voltage (V)
    "tboard",  # Board temperature (°C)
    "tjunc",   # TEC junction temperature (°C)
]

print("Laser and temperature status:")

# Read and print each parameter
for param in status_params:
    try:
        value = ctl.get(param)
        value = float(value)  # Convert the returned string to float
        print(f"{param.upper():<6} : {value}")
    except Exception as e:
        print(f"{param.upper():<6} : Command not available ({e})")
