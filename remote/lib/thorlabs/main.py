import pyvisa, time, numpy as np, sys

def main():
    rm = None
    device = None
    try:
        rm = pyvisa.ResourceManager()

        # query with print(rm.list_resources())
        instr = rm.open_resource('USB0::4883::32882::P2009712::0::INSTR')
        
        #print the device information
        print(instr.query("SYST:SENS:IDN?"))
        
        #turn on auto-ranging
        instr.write("SENS:RANGE:AUTO ON")
        #set wavelength setting, so the correct calibration point is used
        instr.write("SENS:CORR:WAV 1550")
        #set units to Watts
        instr.write("SENS:POW:UNIT W")
        #set averaging to 1000 points
        instr.write("SENS:AVER:20")

        #read the power
        #print (instr.query("MEAS:POW?"))
        

        t0 = time.time()

        count = 0
        i = 0
        power_mem = np.zeros(100)

        while time.time()-t0 < 1000:
            #print("power", power_meter.read)
            power = instr.query("MEAS:POW?")
            power = float(power)
            i = np.mod(count, 100)
            power_mem[i] = power
            
            sys.stdout.write(format(power*1e9, '.3f')+" nW   "+format(power_mem.mean()*1e9, '.3f')+" nW   "+format(power*1e6, '.3f')+" uW   "+format(power_mem.min()*1e6, '.3f')+" uW   "+format(power_mem.max()*1e6, '.3f')+" uW  \r")
            sys.stdout.flush()
            time.sleep(0.1)
            count = count + 1

    finally:
        #Close device in any case
        if device is not None:
            try:
                device.close()
            except Exception:
                pass

        #Close resource manager in any case
        if rm is not None:
            try:
                instr.close()
            except Exception:
                pass

        #close out session
        rm.close()

if __name__ == "__main__":
    main()
