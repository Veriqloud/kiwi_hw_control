import socket, json, os, time
from lib.visuals import mylogger
from enum import Enum


# receive an exact number of bytes
def rcv_exact(conn, l):
    m = bytes(0)
    while len(m)<l:
        m += conn.recv(l - len(m))
    return m


class TcpServer():
    """Create a TCP socket"""

    def __init__(self, program_name, player=None):
        """
        program_name: name of the owner of the socket; from network file; e.g. hws
        player: for testing on local machine; alice or bob
        """
        self.osenv = os.environ
        self.logger = mylogger()
        # make sure QLINE_CONFIG_DIR is set and files exist
        if 'QLINE_CONFIG_DIR' not in self.osenv:
            self.logger.error('please set QLINE_CONFIG_DIR')
            exit()
        # load config files; if player is given, the config is in a subdirectory (on local machine for testing)
        if player:
            network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], player, 'network.json')
        else: 
            network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], 'network.json')
        if not os.path.exists(network_file):
            self.logger.error(network_file+' does not exist')
            exit()
        with open(network_file, 'r') as f:
            network = json.load(f)
        myname = network['myname']
        port = network['port'][program_name]
        host = network['ip'][myname]
        # create socket and listen
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # block and retry if socket cannot be created
        while True:
            try:
                self.sock.bind((host, port))
                break
            except Exception as e:
                self.logger.warning(f"Cannot create socket on {host}:{port} due to error: {e}. Retrying in 10 sec.")
                time.sleep(10)
                continue

        self.sock.listen()
        self.logger.info(f"listening on {host}:{port}")

    # handle client in background
    def accept(self):
        conn, addr = self.sock.accept()  # Accept incoming connection
        self.logger.info(f"connected by {addr}")
        return (conn, addr)





class TcpClient():
    """Connect to a TCP socket"""

    def __init__(self, program_name, player, use_localhost=False):
        """
        program_name: name of the owner of the socket; from network file; e.g. hws
        player: alice or bob
        use_localhost: use localhost and take port from ports_for_localhost.json
        """

        self.osenv = os.environ
        self.logger = mylogger()
        # make sure QLINE_CONFIG_DIR is set and files exist
        if 'QLINE_CONFIG_DIR' not in self.osenv:
            self.logger.error('please set QLINE_CONFIG_DIR')
            exit()
        
        if use_localhost:
            ports_for_localhost_file = os.path.join(os.environ['QLINE_CONFIG_DIR'], 'ports_for_localhost.json')
            if not os.path.exists(ports_for_localhost_file):
                self.logger.error(ports_for_localhost_file+' does not exist')
                exit()
            with open(ports_for_localhost_file, 'r') as f:
                ports_for_localhost = json.load(f)
                host = 'localhost'
                port = ports_for_localhost[program_name]
        else:
            network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], player+'/network.json')
            if not os.path.exists(network_file):
                self.logger.error(network_file+' does not exist')
                exit()
            with open(network_file, 'r') as f:
                network = json.load(f)
            myname = network['myname']
            port = network['port'][program_name]
            host = network['ip'][myname]

        self.socket = socket.socket()
        # block and retry if socket cannot be connected to 
        while True:
            try:
                self.socket.connect((host, port))
                self.logger.info(f"connected to {host}:{port}")
                break
            except Exception as e:
                self.logger.warning(f"Cannot connect to socket on {host}:{port} due to error: {e}. Retrying in 5 sec.")
                time.sleep(5)
                continue

    def send(self, message):
        """
        message: 
        """
        if type(message) == HwsCommand:  
            print("ok")
        else:
            print(type(message))

        #self.socket.sendall(data)





# define commands here to avoid spelling issues
class HwsCommand(Enum):
    SAVE= "save"
    LOAD= "load"
    CLEAN= "clean"

class MessageType(Enum):
    COMMAND= 1
    STR= 2
    INT_32= 3
    INT_64= 4
    DOUBLE= 5






# for testing
def main():
    import threading

    def alice():
        server = TcpServer("hw", "alice")
        conn, addr = server.accept()
        m = conn.rcv_exact(4)
        print(m)

    def client():
        conn = TcpClient("hw", "alice")
        c = HwsCommand.SAVE
        conn.send(c)

    t1 = threading.Thread(target=alice)
    t2 = threading.Thread(target=client)

    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__=="__main__":
    main()






