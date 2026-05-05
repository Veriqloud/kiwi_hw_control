import struct, socket, os, numpy as np, time

alice = socket.socket()
alice.connect(("192.168.1.50", 20000))

# receive double
def rcv_d():
    m = alice.recv(8)
    value = struct.unpack('d', m)[0]
    return value

vca = np.linspace(0,5,51)
power = []

for v in vca:
    os.system("python ~/vqprojects/kiwi_hw_control/local/hw_alice.py set --vca "+str(v))
    time.sleep(0.1)
    alice.sendall(b"s")

    p = rcv_d()
    power.append(p)
    print(v, p)


np.savetxt("calib.txt", np.array([vca, power]).transpose())
alice.sendall(b"t")

alice.close()






