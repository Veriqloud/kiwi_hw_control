#!/bin/python

import tkinter as tk
from tkinter import ttk
from tkinter import font

import os, argparse, argcomplete, socket, json, time, threading, queue, re

# this is a client receiving contents of the logfiles similar to tail -f
# graphics is running in the main thread. Each tcp connection is managed in a different thread. We have 3 threads on total.
# updates are done using queues and event_generate to trigger window update

# log files to display
FILE_NAMES = ['hw.log', 'hws.log', 'mon.log', 'hwi.log', 'gc.log', 'node.log', 'kms.log']

# for stopping threads: read with timeout on socket and check for stop flag
TCP_TIMEOUT = 1
STOP_THREADS = threading.Event()

# add method to tk.Text class for color definition
def define_color(self):
    self.tag_configure("black", foreground="black")
    self.tag_configure("red", foreground="darkred")
    self.tag_configure("green", foreground="darkgreen")
    self.tag_configure("yellow", foreground="darkorange")
    self.tag_configure("blue", foreground="blue")
    self.tag_configure("magenta", foreground="darkmagenta")
    self.tag_configure("cyan", foreground="darkcyan")
    self.tag_configure("gray", foreground="gray")
    # tag to make default font bold
    default_font = font.nametofont("TkFixedFont")
    bold_font = default_font.copy()
    bold_font.configure(weight="bold")
    self.tag_configure("bold", font=bold_font)
    self.tag_configure("default", font=default_font)

tk.Text.define_color=define_color

# colored insert

ANSI_TO_TAG = {
    "1": "bold",
    "2": "gray",
    "30": "black",
    "31": "red",
    "32": "green",
    "33": "yellow",
    "34": "blue",
    "35": "magenta",
    "36": "cyan",
    "37": "gray"
}


ANSI_PATTERN = re.compile(r'\x1b\[([0-9;]+)m')
# colored insert for tk.Text from strings with escape sequences
def cinsert(self, index, string_with_excape_secuence):
    pos = 0
    end = 0
    color = "black"
    font = "default"
    # insert text and change color
    for match in ANSI_PATTERN.finditer(string_with_excape_secuence):
        start, end = match.span()
        if start > pos:
            text = string_with_excape_secuence[pos:start]
            self.insert(index, text, (color, font))
        command = match.group(1)
        if ";" in command:
            subcommands = command.split(";")
            if len(subcommands)==2:
                if subcommands[0] == "1":
                    font="bold"
                else:
                    font="default"
                colortag = subcommands[-1]
            else:
                print("rgb not supported")
        else:
            colortag=command
            font="default"

        color = ANSI_TO_TAG.get(colortag)
        pos = end
    # insert remaining text
    if end!=len(string_with_excape_secuence):
        text = string_with_excape_secuence[end:]
        self.insert(index, text, (color, font))

tk.Text.cinsert=cinsert

# TCP connection to server
class Connection():
    def __init__(self, use_localhost=False, player='alice'):
        osenv = os.environ
        # make sure QLINE_CONFIG_DIR is set and files exist
        if 'QLINE_CONFIG_DIR' not in osenv:
            exit('please set QLINE_CONFIG_DIR')
        # load config files
        network_file = os.path.join(osenv['QLINE_CONFIG_DIR'], player+'/network.json')
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
        self.sock.settimeout(TCP_TIMEOUT)
        self.sock.connect((host, port))
        print("connected to server "+player)

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
        main_frame.rowconfigure(1, weight=0)
        
        # for displaying which tab had an error 
        self.haserror = {}
        self.haserror['alice'] = len(FILE_NAMES)*[False]
        self.haserror['bob'] = len(FILE_NAMES)*[False]
        self.errorin = {}
        self.errorin['alice'] = tk.StringVar()
        self.errorin['bob'] = tk.StringVar()
        # the actual logs
        self.logtext = {}
        self.logtext['alice'] = []
        self.logtext['bob'] = []

        # create the frames
        for i, player in enumerate(['alice', 'bob']):
            notebook = ttk.Notebook(main_frame)
            notebook.grid(row=0, column=i, sticky="nsew", padx=(0, 5))

            error_frame = ttk.Frame(main_frame, padding=10)
            error_frame.grid(row=1,column=i, sticky="ew", padx=(0,5))
            label = ttk.Label(error_frame, textvariable=self.errorin[player])
            label.pack(side="left")
            print("cerating botton for player", player, i)
            button = ttk.Button(error_frame, text="clear error ", command=lambda p=player: self.on_clear_error(p))
            button.pack(side="right")

            for i in range(len(FILE_NAMES)):
                tab = ttk.Frame(notebook)
                notebook.add(tab, text=FILE_NAMES[i].split(".")[0])
                scrollbar = ttk.Scrollbar(tab)
                scrollbar.pack(side="right", fill="y")
                
                text = tk.Text(tab, wrap="word", yscrollcommand=scrollbar.set)
                text.pack(fill="both", expand=True, padx=0, pady=0)
                text.define_color()
                scrollbar.config(command=text.yview)
                self.make_readonly(text)
                self.logtext[player].append(text)
        

        style = ttk.Style()
        default_font = font.nametofont("TkFixedFont")
        style.configure("TNotebook.Tab", font=default_font)

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
        if 'clear' in who:
            player = who.split("_")[0]
            self.logtext[player][tabnumber].delete("1.0", "end")
            self.logtext[player][tabnumber].insert("1.0", s)
        else:
            # if scrollbar is at bottom, move to bottom
            autoscroll = self.logtext[who][tabnumber].yview()[1] == 1.0
            self.logtext[who][tabnumber].cinsert("end", s)
            if autoscroll:
                self.logtext[who][tabnumber].see("end")

    def on_clear_error(self, player):
        print("clear ", player)
        self.haserror[player] = len(FILE_NAMES)*[False]
        self.errorin[player].set("")
    
    # function to be triggered from other thread
    def on_data_ready(self, event):
        try:
            while True:
                (who, tabnumber, s) = self.q.get_nowait()
                self.attach(who, tabnumber, s)
                errorpattern = re.compile(r'\berror\b(?![\s_]+(rate|correction)\b)', re.IGNORECASE)
                if bool(errorpattern.search(s)):
                    self.haserror[who][tabnumber]=True
                    s = "error in "
                    for i in range(len(FILE_NAMES)):
                        if self.haserror[who][i]:
                            s = s+FILE_NAMES[i].split(".")[0]+" "
                    self.errorin[who].set(s)
        except queue.Empty:
            pass


# handle connection to alice/bob (to be launched in a separate thread)
def handle_connection(use_localhost, q, root, player='alice'):
    # reconnect forever
    while True:
        # wait for connection
        while True:
            if STOP_THREADS.is_set():
                return 
            try:
                c = Connection(use_localhost, player)
                # clear text
                for i in range(len(FILE_NAMES)):
                    q.put((player+'_clear', i, ""))
                    root.event_generate("<<DataReady>>", when="tail")
                root.event_generate("<<DataReady>>", when="tail")
                break
            except ConnectionRefusedError or TimeoutError:
                # update text for all tabs: Alice/Bob unavailable
                for i in range(len(FILE_NAMES)):
                    q.put((player+'_clear', i, player+" unavailable\n"))
                    root.event_generate("<<DataReady>>", when="tail")
                time.sleep(1)
                continue
        # receive string from server
        while True:
            if STOP_THREADS.is_set():
                return 
            try:
                fileindex, s = c.receivestring()
            except TimeoutError:
                continue
            # check for disconnection
            if fileindex == -1:
                break
            # update text
            q.put((player, fileindex, s))
            root.event_generate("<<DataReady>>", when="tail")
        


def main():

    # argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--use_localhost", action="store_true", 
                        help="connect to localhost instead of ip from network.json; e.g. when port forwarding")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()


    ##########
    q = queue.Queue()
    g = Graphics(q)

    thread_alice = threading.Thread(target=handle_connection, args = (args.use_localhost, q, g.root, 'alice'))
    thread_alice.start()
    thread_bob = threading.Thread(target=handle_connection, args = (args.use_localhost, q, g.root, 'bob'))
    thread_bob.start()

    g.root.mainloop()

    STOP_THREADS.set()

    thread_alice.join()
    thread_bob.join()








if __name__=="__main__":
    main()










