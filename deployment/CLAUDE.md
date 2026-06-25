# Building and Running the QKD Simulator

This guide describes how to build and run the VeriQloud QKD **simulator** stack for
local development and testing. The simulator emulates the quantum hardware for both
Alice (the photon source) and Bob (the photon detector) using a preshared seed, so no
real quantum channel is needed.

## Components

The simulator stack is assembled from three repositories, expected to be checked out as
sibling directories:

```
<workspace>/
├── hw_sim/            # the hardware simulator (binary: simulator)
├── kiwi_hw_control/   # this repo: gc (global counter), qber (diagnostics), gen_config
└── qline_backend/     # node (post-processing) + kms (ETSI-014 API)   [full stack only]
```

Two stacks are commonly run:

- **Diagnostic stack** `simulator → gc → qber` — fastest way to confirm the simulated
  hardware is healthy. `qber` prints the 4×4 correlation matrix, the QBER, and the
  decoy-state counts.
- **Full stack** `simulator → gc → node → kms` — the complete key-distribution
  pipeline, exposing keys over the ETSI-014 HTTP API.

Data flows, per player: `simulator → gc → {qber | node} → kms`.

## Prerequisites

- A recent Rust toolchain (`rustup default stable`). Some crates use `edition = "2024"`,
  so Rust ≥ 1.85 is required.
- A C compiler / build tools.
- All three repositories checked out as siblings (see above).

## 1. Build the binaries

```bash
# simulator (in hw_sim)
cd hw_sim && cargo build --release && cd ..

# gc + qber (in this repo)
cd kiwi_hw_control/gc   && cargo build --release && cd ..
cd qber                 && cargo build --release && cd ..
cd config/gen_config    && cargo build --release && cd ../../..

# full stack only: node + kms (in qline_backend)
cd qline_backend && cargo build --release && cd ..
```

Binaries land in each crate's `target/release/`:
`hw_sim/target/release/simulator`, `kiwi_hw_control/{gc,qber}/target/release/{alice,bob}`,
`kiwi_hw_control/config/gen_config/target/release/gen_config`,
`qline_backend/target/release/{node,km-server}`.

> Offline / no-repo-access note: the inter-repo dependencies in the various `Cargo.toml`
> files are `git = "ssh://git@github.com/Veriqloud/..."`. With repo access (e.g. an SSH
> deploy key) cargo fetches them automatically. Without it, temporarily rewrite those
> dependencies to local `path = "..."` pointing at the sibling checkouts.

## 2. Generate the configuration

Configuration for every component and player is generated from a single **meta config**
by `gen_config` (it replaces the old `auto_setup` tool). An example pair for the
simulator lives in `config/sim/`:

- `config/sim/meta_config.json` — ports, file paths, KMS/node settings (incl. decoy-state
  parameters for the full stack).
- `config/sim/sim_config.json` — the simulator backend parameters (`angles`, `seed`,
  `eta`, `qberr`, `pulse_distance`, and an optional `decoy_states` block).

```bash
cd config/sim
../gen_config/target/release/gen_config -c meta_config.json -s sim_config.json
```

This writes per-player config files into `alice/` and `bob/`:
`sim.json`, `gc.json`, `qber.json`, `node.json`, `kms.json`, `network.json`.

### Decoy states

To run in decoy mode, include a `decoy_states` block in `sim_config.json`:

```json
"decoy_states": { "mu1": 0.5, "mu2": 0.1, "p1": 0.7 }
```

and the corresponding node parameters under `node` in `meta_config.json`:

```json
"decoystates": { "mu1": 0.5, "mu2": 0.1, "p1": 0.7,
                 "esec": 1e-10, "ecor": 1e-10, "K": 19,
                 "intensity_bit_mapping": "TrueMeansMu1" }
```

Omitting these blocks runs the standard (non-decoy) protocol.

## 3. Run the diagnostic stack (simulator → gc → qber)

Run each command in its own terminal. **Start order matters**: `simulator` first, then
`gc`, then `qber` (Bob before Alice). Paths below assume you run from `config/sim`.

```bash
# 1. simulators
hw_sim/target/release/simulator --config-path alice/sim.json
hw_sim/target/release/simulator --config-path bob/sim.json

# 2. global counter
kiwi_hw_control/gc/target/release/bob   -c bob/gc.json
kiwi_hw_control/gc/target/release/alice -c alice/gc.json

# 3. qber (Bob first; Alice takes a positional count = clicks to average)
kiwi_hw_control/qber/target/release/bob        -c bob/qber.json
kiwi_hw_control/qber/target/release/alice 6400 -c alice/qber.json
```

### Reading the qber output

`qber alice` prints, per batch:

- A 4×4 correlation matrix (strong correlated entries, ~1 on the noise floor).
- `qber (alice, bob, total)` — should match the configured `qberr` (e.g. ~5% for
  `qberr: 0.05`).
- `decoy [n0, n1, n2, n3]` — histogram of the per-pulse intensity field. In standard
  mode all counts fall in bucket 0 (`[N, 0, 0, 0]`). With decoy enabled the counts split
  between mu1 and mu2 according to `p1` (e.g. `p1: 0.7` → ~70 % in bucket 0, ~30 % in
  bucket 1).

## 4. Run the full stack (simulator → gc → node → kms)

Same as above through `gc`, but replace `qber` with `kms` then `node`. **The KMS must be
started before node**: node connects as a client to the KMS key-handoff unix socket
(`kms.json` → `ipc_config.unix_socket_path`) and aborts if it is not yet available.

```bash
# after simulators + gc are up:
qline_backend/target/release/km-server -c alice/kms.json
qline_backend/target/release/km-server -c bob/kms.json
qline_backend/target/release/node      -c alice/node.json
qline_backend/target/release/node      -c bob/node.json
```

Notes:

- `node` loads its libp2p identity as an RSA PKCS#8 key from the path in `node.json`
  (`libp2p.pathedkeypair`); that file must exist and its PeerId must match the `Qm…` id
  in the config. Generate keys with `qline_backend`'s `convenience_tools`
  (`genp2p` / `showpeerid`).
- The KMS (with `AutoGen` authentication + `Local`/mDNS networking) generates its own
  keys at startup and discovers its peer automatically; it needs no key files.
- The two `node` instances discover each other over libp2p (Alice is the boot node).

## Stopping and cleanup

Stop the processes (Ctrl-C in each terminal, or kill by PID). The simulator recreates its
FIFOs/sockets under the configured paths (default `/tmp`) on each start; stale files owned
by another user can block startup with "Operation not permitted" — remove them first.
