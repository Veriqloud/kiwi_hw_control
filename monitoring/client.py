#!/bin/python

import os, argparse, argcomplete, socket, json, time

# this is a client receiving contents of the logfiles similar to tail -f

FILE_NAMES = ['hw.log', 'hws.log']

# TCP connection to server
class Connection():
    def __init__(self, use_localhost=False, player='alice'):
        osenv = os.environ
        # make sure QLINE_CONFIG_DIR is set and files exist
        if 'QLINE_CONFIG_DIR' not in osenv:
            exit('please set QLINE_CONFIG_DIR')
        # load config files
        network_file = os.path.join(osenv['QLINE_CONFIG_DIR'], 'alice/network.json')
        if not os.path.exists(network_file):
            exit(network_file+' does not exist; please run gen_config or similar')
        ports_for_localhost_file = os.path.join(osenv['QLINE_CONFIG_DIR'], 'ports_for_localhost.json')
        # get ip and port from config
        if use_localhost:
            with open(ports_for_localhost_file, 'r') as f:
                ports_for_localhost = json.load(f)
            port = ports_for_localhost['showlogs_'+player]
            host = 'localhost'
        else:
            with open(network_file, 'r') as f:
                network = json.load(f)
            port = network['port']['showlogs']
            host = network['ip'][player]
        # connect to server
        self.sock = socket.socket()
        self.sock.connect((host, port))
        print("connected to server")

    # receive an exact number of bytes; return zero bytes if zero bytes are received (meaning connection closed)
    def receiveexact(self, n):
        m = self.sock.recv(n)
        if len(m)==n:
            return m
        while len(m)<n:
            newm = self.sock.recv(n-len(m))
            if len(newm)==0:
                return b""
            m += newm
        return m

    # receive fileindex and a string of unknown length; 
    # if length is zero (connection closed) close the socket and return empty string
    def receivestring(self):
        b = self.receiveexact(5)
        l = int.from_bytes(b[:4], byteorder='little')
        fileindex = int.from_bytes(b[4:5], 'little')
        m = self.receiveexact(l)
        if len(m)==0:
            print("server closed socket")
            self.sock.close()
            return -1, ""
        s = m.decode().strip()
        return fileindex, s
    

class Graphics():
    def __init__(self):
        root = tk.Tk()
        root.geometry("400x300")
        root.title("Logs")

        main_frame=ttk.Frame(root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # alice
        alice_notebook = ttk.Notebook(main_frame)
        alice_notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.text_alice = [] 
        for i in range(len(FILE_NAMES)):
            text_alice.append(tk.StringVar(value="trying to connect to Alice"))
            alice_tab = ttk.Frame(alice_notebook)
            alice_notebook.add(alice_tab, textvariable=FILE_NAMES[i])
            ttk.Label(alice_tab, textvariable=text_alice[-1]).pack(padx=10, pady=10)
        
        # bob
        alice_notebook = ttk.Notebook(main_frame)
        alice_notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.text_bob = [] 
        for i in range(len(FILE_NAMES)):
            text_bob.append(tk.StringVar(value="trying to connect to Alice"))
            alice_tab = ttk.Frame(alice_notebook)
            alice_notebook.add(alice_tab, textvariable=FILE_NAMES[i])
            ttk.Label(alice_tab, textvariable=text_bob[-1]).pack(padx=10, pady=10)

    def attach(self, who, tabnumber, s):
        if who=='alice':
            self.text_alice[tabnumber].set(self.text_alice[tabnumber].get()+s)
        elif who=='bob':
            self.text_bob[tabnumber].set(self.text_bob[tabnumber].get()+s)




def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--use_localhost", action="store_true", 
                        help="connect to localhost instead of ip from network.json; e.g. when port forwarding")
    
    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    c = Connection(args.use_localhost, 'alice')

    while True:
        fileindex, s = c.receivestring()
        if s == "":
            break
        print(FILE_NAMES[fileindex], s)



if __name__=="__main__":
    main()

