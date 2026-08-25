#!/usr/bin/env python3
# Read-only one-shot mon probe. Persistent connection per node (exactly like
# kiwi_hw_control/local/mon.py). Issues ONLY the read-only get_* commands that
# mon.py --status issues in one iteration; does NOT call update_errorflag
# (set_error/clear_error) and does NOT loop/plot.
import socket, json, struct, os, sys

CFG = os.environ.get('QLINE_CONFIG_DIR')
if not CFG:
    sys.exit("please set QLINE_CONFIG_DIR")
# --use_localhost: connect via localhost tunnels (port_forwarding.sh) instead of node IPs.
use_localhost = '--use_localhost' in sys.argv[1:]
# --quiet: drop the progress lines so stdout is nothing but the JSON, for
# callers that parse it (run_qkd.sh).
quiet = '--quiet' in sys.argv[1:]
# --brief: only the state queries -- rng, services, pci, wrs, qkd_ready, node
# stats. Skips everything that reads the optics or the SPI chips, which is both
# slow and, in get_spd_temp's case, able to abort mon outright (libusb assertion
# in the AUREA path). Bring-up wants the state, not the instruments.
brief = '--brief' in sys.argv[1:]
network = json.load(open(os.path.join(CFG, 'alice/network.json')))

if use_localhost:
    lp = json.load(open(os.path.join(CFG, 'ports_for_localhost.json')))
    targets = {'alice': ('localhost', lp['mon_alice']), 'bob': ('localhost', lp['mon_bob'])}
else:
    mon_port = network['port']['mon']
    targets = {'alice': (network['ip']['alice'], mon_port), 'bob': (network['ip']['bob'], mon_port)}

def conn(host, port):
    s = socket.socket(); s.settimeout(10); s.connect((host, port)); return s
def sendc(s, c):
    s.sendall(len(c).to_bytes(2, 'little') + c.encode())
def recv_exact(s, l):
    # recv returns b'' forever once the peer is gone, so a bare accumulate loop
    # spins at 100% CPU instead of failing -- and mon does die, e.g. on the
    # libusb abort in get_spd_temp. Raise so the caller sees it.
    m = b''
    while len(m) < l:
        chunk = s.recv(l - len(m))
        if not chunk:
            raise ConnectionError("connection closed by mon")
        m += chunk
    return m
def rcvc(s):
    l = int.from_bytes(recv_exact(s, 2), 'little'); return recv_exact(s, l).decode().strip()
def rcv_i(s): return struct.unpack('i', recv_exact(s, 4))[0]
def rcv_d(s): return struct.unpack('d', recv_exact(s, 8))[0]

def p(*a):
    if quiet:
        return
    print(*a); sys.stdout.flush()

alice = conn(*targets['alice'])
p("connected alice")
bob = conn(*targets['bob'])
p("connected bob")

out = {}
sendc(alice, 'get_rng_status'); out['rng_alice'] = rcv_i(alice); p("rng_alice done")
sendc(bob,   'get_rng_status'); out['rng_bob']   = rcv_i(bob);   p("rng_bob done")

if not brief:
    sendc(alice, 'get_fifo_status'); out['fifo_alice'] = [rcv_i(alice) for _ in range(6)]  # 4 ddr, rng_err sticky, rng_err raw; p("fifo_alice done")
    sendc(bob,   'get_fifo_status'); out['fifo_bob']   = [rcv_i(bob) for _ in range(6)]  # 4 ddr, rng_err sticky, rng_err raw;   p("fifo_bob done")

sendc(alice, 'get_server_status'); out['server_alice'] = [rcv_i(alice) for _ in range(4)]; p("server_alice done")
sendc(bob,   'get_server_status'); out['server_bob']   = [rcv_i(bob) for _ in range(4)];   p("server_bob done")

if not brief:
    sendc(bob, 'get_counts')
    out['counts'] = {'total': rcv_i(bob), 'click0': rcv_i(bob), 'click1': rcv_i(bob)}; p("counts done")

    sendc(bob, 'get_spd_temp'); out['spd_temp'] = rcv_d(bob); p("spd_temp done")

sendc(alice, 'get_pci_status'); out['pci_alice'] = rcvc(alice); p("pci_alice done")
sendc(bob,   'get_pci_status'); out['pci_bob']   = rcvc(bob);   p("pci_bob done")

if not brief:
    sendc(alice, 'get_gc'); gc_a = rcv_d(alice)
    sendc(bob,   'get_gc'); gc_b = rcv_d(bob)
    out['gc_alice_s'] = gc_a/40e6; out['gc_bob_s'] = gc_b/40e6
    out['gc_diff_ms'] = (gc_b-gc_a)/40e6*1000; p("gc done")

sendc(alice, 'get_wrs_ip_status'); out['wrs_ip_alice'] = rcv_i(alice)
sendc(bob,   'get_wrs_ip_status'); out['wrs_ip_bob']   = rcv_i(bob); p("wrs_ip done")

sendc(alice, 'get_qkd_ready'); out['qkd_ready'] = rcvc(alice); p("qkd_ready done")

sendc(alice, 'get_node_stats')
out['key_length'] = rcv_i(alice); out['qber'] = rcv_d(alice); p("node_stats done")

alice.close(); bob.close()
p("=== RESULT ===")
print(json.dumps(out, indent=2))
