#!/usr/bin/env python3
# Read-only one-shot mon probe. Persistent connection per node (exactly like
# kiwi_hw_control/local/mon.py). Issues ONLY the read-only get_* commands that
# mon.py --status issues in one iteration; does NOT call update_errorflag
# (set_error/clear_error) and does NOT loop/plot.
import socket, json, struct, os, sys

CFG = os.environ.get('QLINE_CONFIG_DIR') or os.path.expanduser('~/kiwi_hw_control/config/qline1')
network = json.load(open(os.path.join(CFG, 'alice/network.json')))
port = network['port']['mon']

def conn(host):
    s = socket.socket(); s.settimeout(10); s.connect((host, port)); return s
def sendc(s, c):
    s.sendall(len(c).to_bytes(2, 'little') + c.encode())
def recv_exact(s, l):
    m = b''
    while len(m) < l: m += s.recv(l - len(m))
    return m
def rcvc(s):
    l = int.from_bytes(recv_exact(s, 2), 'little'); return recv_exact(s, l).decode().strip()
def rcv_i(s): return struct.unpack('i', recv_exact(s, 4))[0]
def rcv_d(s): return struct.unpack('d', recv_exact(s, 8))[0]

def p(*a):
    print(*a); sys.stdout.flush()

alice = conn(network['ip']['alice'])
p("connected alice")
bob = conn(network['ip']['bob'])
p("connected bob")

out = {}
sendc(alice, 'get_rng_status'); out['rng_alice'] = rcv_i(alice); p("rng_alice done")
sendc(bob,   'get_rng_status'); out['rng_bob']   = rcv_i(bob);   p("rng_bob done")

sendc(alice, 'get_fifo_status'); out['fifo_alice'] = [rcv_i(alice) for _ in range(6)]; p("fifo_alice done")
sendc(bob,   'get_fifo_status'); out['fifo_bob']   = [rcv_i(bob) for _ in range(6)];   p("fifo_bob done")

sendc(alice, 'get_server_status'); out['server_alice'] = [rcv_i(alice) for _ in range(4)]; p("server_alice done")
sendc(bob,   'get_server_status'); out['server_bob']   = [rcv_i(bob) for _ in range(4)];   p("server_bob done")

sendc(bob, 'get_counts')
out['counts'] = {'total': rcv_i(bob), 'click0': rcv_i(bob), 'click1': rcv_i(bob)}; p("counts done")

sendc(bob, 'get_spd_temp'); out['spd_temp'] = rcv_d(bob); p("spd_temp done")

sendc(alice, 'get_pci_status'); out['pci_alice'] = rcvc(alice); p("pci_alice done")
sendc(bob,   'get_pci_status'); out['pci_bob']   = rcvc(bob);   p("pci_bob done")

sendc(alice, 'get_gc'); gc_a = rcv_d(alice)
sendc(bob,   'get_gc'); gc_b = rcv_d(bob)
out['gc_alice_s'] = gc_a/40e6; out['gc_bob_s'] = gc_b/40e6
out['gc_diff_ms'] = (gc_b-gc_a)/40e6*1000; p("gc done")

sendc(alice, 'get_wrs_ip_status'); out['wrs_ip_alice'] = rcv_i(alice)
sendc(bob,   'get_wrs_ip_status'); out['wrs_ip_bob']   = rcv_i(bob); p("wrs_ip done")

sendc(alice, 'get_node_stats')
out['key_length'] = rcv_i(alice); out['qber'] = rcv_d(alice); p("node_stats done")

alice.close(); bob.close()
p("=== RESULT ===")
p(json.dumps(out, indent=2))
