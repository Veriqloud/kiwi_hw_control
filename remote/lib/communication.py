import sys
sys.path.insert(0, '/home/vq-user/hw_control')
sys.path.insert(0, '../')

import socket, json, os, time, struct, gzip, numpy as np
from lib.visuals import mylogger
from enum import Enum

BYTEORDER = 'little'            # for message encoding
if BYTEORDER == 'little':
    BYTEORDER_FOR_STRUCT = '<'
else:
    BYTEORDER_FOR_STRUCT = '>'

SOCKET_RECREATE_WAIT = 10       # wait this many seconds before trying to recreate socket (e.g. no network)
SOCKET_RECONNECT_WAIT = 5       # wait this many seconds before trying to reconnect to socket (e.g. server not up)
#SOCKET_TIMEOUT = 5              # timout on send, recv, etc

# The structure of one full message is: [MessageTyep, length_of_data_in_bytes, data]
# MessateType is 1 byte long; length_of_data_in_bytes is 3 bytes long
# Here are the message types
class MessageType(Enum):
    COMMAND = 1 # string message
    INT = 2     # variable bytelength, calculated from .bit_length()
    FLOAT = 3   # 64bit
    BYTES = 4   # bytes; will be compressed using gzip

# Commands are instructions that tell the other party what to do
# Hws stands for hardware system; it controls an Alice-Bob pair
class HwsCommand(Enum):
    SAVE = "save"
    LOAD = "load"
    CLEAN = "clean"
    ACK = "ack"     # acknowledged



# add some functions to a socket instance
# original existing functions: send, sendall, recv
class ExtendSocket():
    def __init__(self, sock):
        self._base = sock
    
    def __getattr__(self, name):
        return getattr(self._base, name)

    # receive an exact number of bytes
    def rcv_exact(self, l):
        m = self.recv(l)
        while len(m)<l:
            m2 = self.recv(l - len(m))
            if len(m2) == 0:
                raise ConnectionError("received 0-len message")
            m += self.recv(l - len(m))
        return m

    def psnd(self, data):
        """
        package and send
        data: must be one of the following types: string, int, float, bytes
        if data is of type bytes, it will be compressed
        """
        if type(data) == HwsCommand:  
            m = MessageType.COMMAND.value.to_bytes(1, BYTEORDER)
            m += len(data.value).to_bytes(3, BYTEORDER)
            m += data.value.encode()
        elif type(data) == int:
            m = MessageType.INT.value.to_bytes(1, BYTEORDER)
            l = (data.bit_length() // 8) + 1
            m += l.to_bytes(3, BYTEORDER)
            m += data.to_bytes(l, BYTEORDER)
        elif type(data) == float:
            m = MessageType.FLOAT.value.to_bytes(1, BYTEORDER)
            m += (8).to_bytes(3, BYTEORDER)
            m += struct.pack(BYTEORDER_FOR_STRUCT+'d', data)
        elif type(data) == bytes:
            m = MessageType.BYTES.value.to_bytes(1, BYTEORDER)
            compressed = gzip.compress(data)
            l = len(compressed)
            if l >= (2<<24):
                raise ValueError(f"Data length of {l} bytes is too long! Needs to be less than {2<<24} bytes.")
            m += l.to_bytes(3, BYTEORDER)
            m += compressed
        else:
            raise ValueError("unknown data type")
        self.send(m)
    
    def prcv(self):
        """
        receive package and return data
        """
        header = self.rcv_exact(4)
        t = header[0]
        l = int.from_bytes(header[1:], BYTEORDER)
        body = self.rcv_exact(l)

        if t == MessageType.COMMAND.value:
            body = body.decode()
            for command in HwsCommand:
                if body==command.value:
                    return command
            raise ValueError(f"received wrong command {body}")
        elif t == MessageType.INT.value:
            return int.from_bytes(body, BYTEORDER)
        elif t == MessageType.FLOAT.value:
            return struct.unpack(BYTEORDER_FOR_STRUCT+'d', body)[0]
        elif t == MessageType.BYTES.value:
            return gzip.decompress(body)
        else:
            raise ValueError(f"received wrong message type {t}")
    
    def ack(self):
        """
        send acknowledge message
        """
        m = HwsCommand.ACK
        self.psnd(m)

    def wait_ack(self):
        """
        receive acknowledge message
        """
        m = self.prcv()
        if m==HwsCommand.ACK:
            pass
        else:
            raise ValueError(f"expected ACK signal; got something else")






class TcpServer():
    """Create a TCP socket from config file and wait for connection"""

    def __init__(self, program_name, player=None, use_wrs=None):
        """
        program_name: name of the owner of the socket; from network file; e.g. hws
        player: for testing on local machine; alice or bob
        use_wrs: use WRS network
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
        if use_wrs:
            myname += '_wrs'
        port = network['port'][program_name]
        host = network['ip'][myname]
        # create socket and listen
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.sock.settimeout(SOCKET_TIMEOUT)

        # block and retry if socket cannot be created
        while True:
            try:
                self.sock.bind((host, port))
                break
            except Exception as e:
                self.logger.warning(f"Cannot create socket on {host}:{port} due to error: {e}. Retrying in 10 sec.")
                time.sleep(SOCKET_RECREATE_WAIT)
                continue

        self.sock.listen()
        self.logger.info(f"listening on {host}:{port}")

    def accept(self):
        conn, addr = self.sock.accept()
        self.logger.info(f"connected by {addr}")
        return ExtendSocket(conn)





class TcpClient():
    """Connect to a TCP socket from config file"""

    def __init__(self, program_name, player, use_localhost=False, use_wrs=False):
        """
        program_name: name of the owner of the socket; from network file; e.g. hws
        player: alice or bob
        use_localhost: use localhost and take port from ports_for_localhost.json
        use_wrs: use WRS network
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
                self.host = 'localhost'
                self.port = ports_for_localhost[program_name]
        else:
            if use_wrs:
                network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], 'network.json')
                player = player+'_wrs'
            else:
                network_file = os.path.join(self.osenv['QLINE_CONFIG_DIR'], player+'/network.json')
            if not os.path.exists(network_file):
                self.logger.error(network_file+' does not exist')
                exit()
            with open(network_file, 'r') as f:
                network = json.load(f)
            self.port = network['port'][program_name]
            self.host = network['ip'][player]

        self.sock = socket.socket()
        #self.sock.settimeout(SOCKET_TIMEOUT)

    def connect(self):
        # block and retry if socket cannot be connected to 
        while True:
            try:
                self.sock.connect((self.host, self.port))
                self.logger.info(f"connected to {self.host}:{self.port}")
                break
            except Exception as e:
                self.logger.warning(f"Cannot connect to socket on {self.host}:{self.port} due to error: {e}. Retrying in 5 sec.")
                time.sleep(SOCKET_RECONNECT_WAIT)
                continue
        return ExtendSocket(self.sock)












# for testing
def main():
    import threading, numpy as np


    def alice():
        print("Hello Alice")
        server = TcpServer("hw", "alice")
        conn = server.accept()
        m = conn.prcv()
        print("Alice got", m)
        m = conn.prcv()
        print("Alice got", m)
        m = conn.prcv()
        print("Alice got", m)

        # receive numpy array
        m = conn.prcv()
        a = np.frombuffer(m, dtype=np.int64)
        print("Alice got", a)

    def client():
        time.sleep(0.01)
        conn = TcpClient("hw", "alice").connect()
        c = HwsCommand.LOAD
        conn.psnd(c)
        i = 51
        conn.psnd(i)
        f = 3.14
        conn.psnd(f)

        # send numpy array
        a = np.array([1, 2, 3], dtype=np.int64)
        b = a.tobytes()
        conn.psnd(b)


    t1 = threading.Thread(target=alice)
    t2 = threading.Thread(target=client)

    t1.start()
    t2.start()
    t1.join()
    t2.join()


if __name__=="__main__":
    main()






