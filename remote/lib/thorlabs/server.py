import pyvisa, struct, socket

# send double
def send_d(conn, value):
    m = struct.pack('d', value)
    conn.sendall(m)


def main():


    rm = None
    device = None
    try:
        rm = pyvisa.ResourceManager()

        # query with print(rm.list_resources())
        instr = rm.open_resource('USB0::4883::32882::P2009712::0::INSTR')
        
        #print the device information
        #print(instr.query("SYST:SENS:IDN?"))
        
        #turn on auto-ranging
        instr.write("SENS:RANGE:AUTO ON")
        #set wavelength setting, so the correct calibration point is used
        instr.write("SENS:CORR:WAV 1550")
        #set units to Watts
        instr.write("SENS:POW:UNIT W")
        #set averaging to 1000 points
        instr.write("SENS:AVER:1000")

        # Create TCP socket
        server_socket = socket.socket()
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("192.168.1.50", 20000))
        server_socket.listen()


        while True:
            conn, addr = server_socket.accept()  # Accept incoming connection

            while conn.recv(1)==b"s":

                power =  float(instr.query("MEAS:POW?"))
                print(power)
                send_d(conn, power)



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
