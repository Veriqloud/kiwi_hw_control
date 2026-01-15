#!/bin/python
import tkinter as tk
from tkinter import ttk
import os, argparse, json, socket


network_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'alice/network.json')
ports_for_localhost_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'ports_for_localhost.json')

alice_online = False
bob_online = False

def connect_to_alice(use_localhost=False):
    global alice_online
    if alice_online:
        return 
    if use_localhost:
        with open(ports_for_localhost_file, 'r') as f:
            ports_for_localhost = json.load(f)
        host = 'localhost'
        port = ports_for_localhost['hw_alice']
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['alice']
        port = network['port']['showlogs']
    try:
        global alice
        print(f"trying to connect to {host}:{port}")
        alice = socket.socket()
        alice.connect((host, port))
        alice_online = True
    except:
        alice_online = False

def connect_to_bob(use_localhost=False):
    if use_localhost:
        with open(ports_for_localhost_file, 'r') as f:
            ports_for_localhost = json.load(f)
        host = 'localhost'
        port = ports_for_localhost['hw_bob']
    else:
        with open(network_file, 'r') as f:
            network = json.load(f)
        host = network['ip']['bob']
        port = network['port']['showlogs']
    
    global bob 
    bob = socket.socket()
    bob.connect((host, port))


def receivestring(socket):
    ml = socket.recv(4)
    print("length ml", len(ml))
    while len(ml)<4:
        ml += socket.recv(4-len(ml))
        print("length ml", len(ml))
    l = int.from_bytes(ml, 'little')
    print("length ", l)
    mr = socket.recv(l)
    while len(mr)<l:
        mr += socket.recv(l-len(mr))
    string = mr.decode().strip()
    return string


#create top_level parser
parser = argparse.ArgumentParser()
parser.add_argument("--use_localhost", action="store_true", 
                    help="connect to localhost instead of ip from network.json; e.g. when port forwarding")

args = parser.parse_args()

root = tk.Tk()
root.geometry("400x300")
root.title("Logs")

main_frame=ttk.Frame(root, padding=10)
main_frame.pack(fill="both", expand=True)

# Configure grid to allow resizing
main_frame.columnconfigure(0, weight=1)
main_frame.columnconfigure(1, weight=1)
main_frame.rowconfigure(0, weight=1)

connection_status_alice = tk.StringVar(value="trying to connect to Alice")
connection_status_bob = tk.StringVar(value="trying to connect to Bob")

hw_alice = tk.StringVar(value="trying to connect to Alice")

# --- Left Notebook ---
left_notebook = ttk.Notebook(main_frame)
left_notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

left_tab1 = ttk.Frame(left_notebook)
left_tab2 = ttk.Frame(left_notebook)

left_notebook.add(left_tab1, text="Left Tab 1")
left_notebook.add(left_tab2, text="Left Tab 2")

ttk.Label(left_tab1, textvariable=hw_alice).pack(padx=10, pady=10)
ttk.Label(left_tab2, text="Content of Left Tab 2").pack(padx=10, pady=10)

# --- Right Notebook ---
right_notebook = ttk.Notebook(main_frame)
right_notebook.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

right_tab1 = ttk.Frame(right_notebook)
right_tab2 = ttk.Frame(right_notebook)

right_notebook.add(right_tab1, text="Right Tab A")
right_notebook.add(right_tab2, text="Right Tab B")

ttk.Label(right_tab1, text="Content of Right Tab A").pack(padx=10, pady=10)
ttk.Label(right_tab2, text="Content of Right Tab B").pack(padx=10, pady=10)

#def client_alice():
#    try:
#        connect_to_alice(args.use_localhost)
#        alice_online = True
#        #hw_alice.set("")
#    except:
#        alice_online = False
#        hw_alice.set("Alice not available")

def update_hw_alice():
    global alice_online
    if not alice_online:
        hw_alice.set("Alice not available")
        root.after(2000, update_hw_alice)
        return 
    else:
        try:
            s = receivestring(alice)
            hw_alice.set(hw_alice.get()+s)
            root.after(2000, update_hw_alice)
        except:
            alice_online = False
            root.after(2000, update_hw_alice)


#def client_bob():
#    try:
#        connect_to_bob(args.use_localhost)
#        bob_online = True
#    except:
#        bob_online = False

def reconnect_alice():
    connect_to_alice(args.use_localhost)
    root.after(2000, reconnect_alice)

reconnect_alice()

root.after(2000, update_hw_alice)

root.mainloop()






