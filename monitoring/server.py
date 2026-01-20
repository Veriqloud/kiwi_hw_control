#!/bin/python
import logging, socket, json, os, argparse, argcomplete, time, threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# this is a server that watches the logfiles and sends changes to the clients. 

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger.info("Start program")

FILE_NAMES = ['hw.log', 'hws.log', 'mon.log', 'hwi.log', 'gc.log', 'node.log', 'kms.log']


# event handler to read log files upon filesystem change
class TailHandler(FileSystemEventHandler):
    def __init__(self, conn, path, observer):
        self.conn = conn
        self.observer = observer
        self.files = []
        for file in FILE_NAMES:
            self.files.append(os.path.join(path, file))
        self.fps = [None]*len(FILE_NAMES)
        self.fsize = [0]*len(FILE_NAMES)
        for i,file in enumerate(self.files):
            try:
                size = os.path.getsize(file)
                fp = open(file)
                fp.seek(0,2)
                self.fps[i] = fp
                self.fsize[i] = size
            except FileNotFoundError:
                logger.warning(file+' does not exist')
                self.fps.append(None)

    # detect modification and send string to client
    def on_modified(self, event):
        for i in range(len(self.files)):
            if event.src_path == self.files[i]:
                # in case of truncation, read the entire file
                if not os.path.isfile(self.files[i]):
                    # ignore event if the file does not exist 
                    # this happens when the file was deleted but some process tries to write t it
                    continue
                size = os.path.getsize(self.files[i])
                if size <= self.fsize[i]:
                    self.fps[i].seek(0)
                self.fsize[i]=size
                s = self.fps[i].read()
                # sometimes the file is read twice and the string is empty
                if s=="":
                    return 
                try:
                    self.sendstring(i, s)
                except (BrokenPipeError, ConnectionAbortedError):
                    logger.info('client disconnected')
                    self.observer.stop()

    # don't panic upon delete
    def on_deleted(self, event):
        for i in range(len(self.files)):
            if event.src_path == self.files[i]:
                logger.info(self.files[i]+' was deleted')
                self.fps[i].close()

    # just reopen the file
    def on_created(self, event):
        for i in range(len(self.files)):
            if event.src_path == self.files[i]:
                logger.info(self.files[i]+' was created')
                fp = open(self.files[i])
                self.fps[i] = fp

    def sendstring(self, fileindex, s):
        # format: 4 bytes length of message + 1 byte fileindex + message
        b = s.encode()
        m = len(b).to_bytes(4, 'little') + fileindex.to_bytes(1, 'little')  + b
        self.conn.sendall(m)


# TCP connection to clients
class Connection():
    def __init__(self, player=None):
        self.osenv = os.environ
        # make sure QLINE_CONFIG_DIR is set and files exist
        if 'QLINE_CONFIG_DIR' not in self.osenv:
            logger.error('please set QLINE_CONFIG_DIR')
            exit()
        # load config files; if player is given, the config is in a subdirectory (on local machine for testing)
        if player:
            network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], player, 'network.json')
        else: 
            network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], 'network.json')
        if not os.path.exists(network_file):
            logger.error(network_file+' does not exist')
            exit()
        with open(network_file, 'r') as f:
            network = json.load(f)
        myname = network['myname']
        port = network['port']['showlogs']
        host = network['ip'][myname]
        # create socket and listen
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen()
        logger.info(f"listening on {host}:{port}")

    # handle client in background
    def handle_client(self):
        conn, addr = self.sock.accept()  # Accept incoming connection
        logger.info(f"connected by {addr}")

        path = os.path.join(self.osenv['HOME'], 'log')

        # use Observer, which creates a new thread and waits for file change
        observer = Observer()
        observer.schedule(TailHandler(conn, path, observer), path, recursive=False)
        observer.start()



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", choices=['alice', 'bob'], 
                        help="define player for testing purposes on local machine")
    
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    c = Connection(args.player)

    while True:
        c.handle_client()

if __name__=="__main__":
    main()














