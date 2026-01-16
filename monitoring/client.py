#!/bin/python

import tkinter as tk
from tkinter import ttk

import os, argparse, argcomplete, socket, json, time, threading, queue

# this is a client receiving contents of the logfiles similar to tail -f
# graphics is running in the main thread. Each tcp connection is managed in a different thread
# updates are done using queues and event_generate to trigger window update

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
        s = m.decode()
        return fileindex, s
    

# manage the graphics window
# use event_generate to update window upon new data; pass data via a queue
class Graphics():
    def __init__(self, q):
        self.q = q
        root = tk.Tk()
        root.geometry("400x300")
        root.title("Logs")

        main_frame=ttk.Frame(root, padding=10)
        main_frame.pack(fill="both", expand=True, anchor="w")
        
        # Configure grid to allow resizing
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # alice
        alice_notebook = ttk.Notebook(main_frame)
        alice_notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.text_alice = [] 
        for i in range(len(FILE_NAMES)):
            alice_tab = ttk.Frame(alice_notebook)
            alice_notebook.add(alice_tab, text=FILE_NAMES[i])
            scrollbar = ttk.Scrollbar(alice_tab)
            scrollbar.pack(side="right", fill="y")
            
            text = tk.Text(alice_tab, wrap="word", yscrollcommand=scrollbar.set)
            text.pack(fill="both", expand=True, padx=0, pady=0)
            scrollbar.config(command=text.yview)
            self.make_readonly(text)
            self.text_alice.append(text)
        
        # bob
        alice_notebook = ttk.Notebook(main_frame)
        alice_notebook.grid(row=0, column=1, sticky="nsew", padx=(0, 5))
        self.text_bob = [] 
        for i in range(len(FILE_NAMES)):
            self.text_bob.append(tk.StringVar(value="trying to connect to Alice"))
            alice_tab = ttk.Frame(alice_notebook)
            alice_notebook.add(alice_tab, text=FILE_NAMES[i])
            ttk.Label(alice_tab, textvariable=self.text_bob[-1]).pack(padx=10, pady=10)
        
        # add function to be triggered from other thread
        root.bind("<<DataReady>>", self.on_data_ready)

        self.root = root

    def make_readonly(self, text):
        text.bind("<Key>", lambda e: "break")
        text.bind("<Control-v>", lambda e: "break")
        text.bind("<Button-2>", lambda e: "break")


    def update_wrap(self, event, label):
        label.configure(wraplength=event.width)

    # attach a string to the text of the tab
    def attach(self, who, tabnumber, s):
        if who=='alice_clear':
            #self.text_alice[tabnumber].config(state="normal")
            self.text_alice[tabnumber].delete("1.0", "end")
            self.text_alice[tabnumber].insert("1.0", s)
            #self.text_alice[tabnumber].config(state="disabled")
        elif who=='alice':
            #self.text_alice[tabnumber].config(state="normal")
            # if scrollbar is at bottom, move to bottom
            autoscroll = self.text_alice[tabnumber].yview()[1] == 1.0
            self.text_alice[tabnumber].insert("end", s)
            if autoscroll:
                self.text_alice[tabnumber].see("end")
            #self.text_alice[tabnumber].config(state="disabled")
            #self.text_alice[tabnumber].set(self.text_alice[tabnumber].get()+s)
        elif who=='bob':
            self.text_bob[tabnumber].set(self.text_bob[tabnumber].get()+s)
    
    # function to be triggered from other thread
    def on_data_ready(self, event):
        try:
            while True:
                (who, tabnumber, s) = self.q.get_nowait()
                print(who, tabnumber, s)
                self.attach(who, tabnumber, s)
        except queue.Empty:
            pass


# handle connection to Alice (to be launched in a separate thread)
def handle_alice(use_localhost, q, root):
    # reconnect forever
    while True:
        # wait for connection
        while True:
            try:
                c = Connection(use_localhost, 'alice')
                # clear text
                for i in range(len(FILE_NAMES)):
                    q.put(('alice_clear', i, ""))
                    root.event_generate("<<DataReady>>", when="tail")
                root.event_generate("<<DataReady>>", when="tail")
                break
            except ConnectionRefusedError:
                # update text for all tabs: Alice unavailable
                for i in range(len(FILE_NAMES)):
                    q.put(('alice_clear', i, "Alice unavailable\n"))
                    root.event_generate("<<DataReady>>", when="tail")
                time.sleep(1)
                continue
        # receive string from server
        while True:
            fileindex, s = c.receivestring()
            # check for disconnection
            if fileindex == -1:
                break
            # update text
            q.put(('alice', fileindex, s))
            root.event_generate("<<DataReady>>", when="tail")
        

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--use_localhost", action="store_true", 
                        help="connect to localhost instead of ip from network.json; e.g. when port forwarding")
    
    argcomplete.autocomplete(parser)

    args = parser.parse_args()


    q = queue.Queue()
    g = Graphics(q)

    threading.Thread(target=handle_alice, args = (args.use_localhost, q, g.root)).start()


    g.root.mainloop()





if __name__=="__main__":
    main()

