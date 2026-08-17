Every program has it's own configuration files. To simplify deployment, `gen_config` can generate all the config files from a single `meta_config.json`.


## Installation

```.bash
cargo build --release
cp target/release/gen_config ~/bin/
```

## Example

For real hardware

```.bash
gen_config -c meta_config_for_real.json
```

For simulator 

```.bash
gen_config -c meta_config_for_sim.json -s sim_config.json
```

For a local simulator run with defaults, no config files are needed at all:

```.bash
gen_config
```

This uses built-in copies of `meta_config_for_sim.json` and `sim_config.json`
(all paths under `/tmp`, everything on `127.0.0.1`), writes the per-player
configs to `./alice` and `./bob`, and — simulator mode only — generates any
missing node RSA keypairs under `./keys` (needs `openssl`), deriving the
libp2p peer ids from the actual key files instead of trusting the meta_config.

In simulator mode the gc command sockets and node-idle flag files are suffixed
`_alice`/`_bob` so both players can run on one machine; the hardware-ready flag
`/tmp/qkd_ready` stays shared and acts as the single local start/stop knob
(see `local/qkd_ready_ctl.sh`).

## The meta_config `node` block

Everything else in the meta_config is addresses, ports and file paths. The `node`
block is where the protocol is configured:

| Field | Meaning |
| --- | --- |
| `key_path` | libp2p RSA keypair (PKCS8 DER) of this node. |
| `qtol` | QBER tolerance: above it a round is discarded instead of turned into key. |
| `clicks_per_round` | Clicks (detection windows) collected from the hardware before postprocessing starts. Not a key size — sifting, parameter estimation, error correction and privacy amplification all shrink it. |
| `key_basis_mode` | `"Symmetrical"` keeps both bases for the final key. `{"Asymmetrical": {"basis": true}}` keeps only the selected one. |
| `decoystates` | Decoy-state parameters, or `null` for plain BB84. |

`clicks_per_round` used to be `key_size_per_round` and counted angle bytes, of
which the hardware packs two per click. A meta_config written before the rename
has to change the key **and double the value** to keep the same round size;
leaving the old key in place makes `gen_config` fail to parse it, which is the
intended outcome — the same file fed to the node directly would silently fall
back to the default instead.

`decoystates` is what switches the node between the standard and the decoy-state
analysis, so its presence is the protocol choice, not a tuning knob:

```json
"decoystates": {
    "mu1": 0.5,
    "mu2": 0.1,
    "p1": 0.7,
    "esec": 1e-10,
    "ecor": 1e-10,
    "K": 19
}
```

`mu1` is the signal intensity and `mu2` the decoy one (below `mu1`), `p1` is the
probability of picking `mu1` — `mu2` gets `1 - p1`. `esec` and `ecor` are the
secrecy and correctness failure probabilities of the final key length bound, and
`K` is the count the Rusca one-decoy bound splits the secrecy budget over.

`mu1`, `mu2` and `p1` describe the source, so they must match the simulator's
`decoy_states` block; `gen_config` refuses to generate configs where the two
disagree. Set `"decoystates": null` to run plain BB84 instead.

All shipped meta configs, simulator and real hardware alike, are in decoy mode.
On real hardware that assumes the FPGA emits the per-pulse intensity bit (bit 2
of the angle byte) and that `decoy_fiber_delay` is set in the hardware
parameters — a node in decoy mode on firmware that does not will read every
pulse as signal intensity.

On hardware these three numbers are *measurements*, not settings: `mu1` and `mu2`
must be the attenuation levels the source actually emits, and `p1` the
probability with which the FPGA picks `mu1` — the decoy RNG (`decoy_rng.service`
on Alice) feeds it unbiased bits, so unless the firmware biases them `p1` is
`0.5`, not the `0.7` the simulator is configured for. `mon`'s
`decoy [n0, n1, n2, n3]` histogram shows the split a running link actually
produces; a `p1` that disagrees with it bounds the key length for the wrong
source.

## The simulator config (`-s`)

`sim_config.json` is hw_sim's own `backend_config`: `gen_config` only splices the
IPC paths into it and writes the result to `alice/sim.json` and `bob/sim.json`.
The shipped file lists every field explicitly and is a verbatim copy of the
`backend_config` block in hw_sim's own
`config_files/{alice,bob}/hw_sim_decoy_config.json`, which is the authoritative
set — keep the two identical rather than tuning this copy on its own:

| Field | Meaning |
| --- | --- |
| `angles`, `seed`, `qberr` | Angle table, PRNG seed, and the intrinsic QBER of the channel. |
| `eta` | Single-photon transmission of the channel. With `decoy_states` the source is an attenuated laser (click probability `1 − e^(−µη)`); without it, an ideal single-photon source, so `eta` *is* the click probability. |
| `pulse_distance` | Seconds between gates. |
| `dead_time` | Seconds the detector is blind after a click; caps the count rate at `1/dead_time`. `0.0` disables. |
| `dark_count_probability` | Dark counts per **gate** (not per second): a rate `D` is `D · pulse_distance`. `0.0` disables. |
| `afterpulse` | Exponential components `{tau, p_ap}` of the afterpulse hazard, referenced to the full gate. `[]` disables it. |
| `software_filter` | Fraction `f` of the gate the software gate keeps. Signal photons are all kept, dark counts and afterpulses only with probability `f`. `1.0` disables filtering. |
| `speedup` | How much faster than real time the simulator delivers. Pure change of clock — the data is identical to a real-time run of the same seed. |
| `decoy_states` | `mu1`/`mu2`/`p1` of the decoy source; absent disables decoy mode. |

`afterpulse` ships with the measured parameters of the reference AUREA detector,
and `eta`, `pulse_distance`, `dark_count_probability`, `software_filter` and
`speedup` are the operating point they were characterised at. These belong
together: a heavily afterpulsing detector only stays below the BB84 error limit
at the point it was fitted for, so replace the whole set at once rather than
moving one value. To simulate an ideal detector instead, clear all of them
together — `"afterpulse": []`, `"dead_time": 0.0`,
`"dark_count_probability": 0.0`, `"software_filter": 1.0`.

`pulse_distance` is the real FPGA gate period (12.5 ns, 80 MHz), which is what
makes `dark_count_probability` `1.25e-6` — 100 cps, a typical InGaAs SPAD. The
15 µs `dead_time` caps the raw rate at 67 kcps and the `0.25` software filter
takes a few percent more off, so at `speedup` 10 the shipped `clicks_per_round`
of 2 000 000 is a round of roughly 3 s. Raising `speedup` much further risks
outrunning the node, which stalls rather than slowing down — see the ceiling
discussion in hw_sim's README before changing it.

## Certificate generation (KMS mTLS)

Pass `--gen-certs` (`-g`) to also generate the KMS mutual-TLS chain. This adapts
the manual `KMS_install/Gen_X509` OpenSSL flow, but fills the certificate SANs
from the meta_config IPs, so there is no `.cnf` to hand-edit. It needs `openssl`
on PATH.

```.bash
gen_config -c meta_config.json --gen-certs
```

It produces, from a single EC root CA:

* a **server** cert per KME (`clientAuth`+`serverAuth`), SAN = the client-facing
  `ip.alice`/`ip.bob` plus `localhost`/`127.0.0.1` (and any `tls.extra_sans`),
* one **client** cert for the SAE / `etsi_client` (`clientAuth`, CN = the SAE id).

Layout of the outputs:

```
certs/          # working dir: CA, .cnf files, gen_certs.sh (re-runnable by hand)
alice/          # ca.crt, cert.pem, eckey_pkcs8.pem  -> deployed to the alice node
bob/            # ca.crt, cert.pem, eckey_pkcs8.pem  -> deployed to the bob node
client/         # ca.crt, sae_cert.pem, sae_key.pem  -> stay local (feed etsi_client)
```

Filenames match the `ca_path`/`cert_path`/`key_path` basenames in the meta_config
`kms` block (the simulator's `_alice`/`_bob` suffixing is preserved). Deploy the
node certs with `deployment/deploy.sh certs`, then set `"authentication": true`
in the meta_config and regenerate the configs.

The CA subject, validity and curve come from the optional `tls` block in the
meta_config (see `meta_config_for_real.json`); sensible VeriQloud defaults are
used when it is absent.

**Regenerating invalidates the previously deployed chain**, so `--gen-certs` is
opt-in and is not part of `deploy.sh all`.


## Building (no private dependencies)

`gen_config` builds the config structs of each program and serializes them. `node`,
`km-server` (kms) and hw_sim's `configs` all live in the private qline_backend repo
(hw_sim is a public project, but its authoritative copy has been vendored into
qline_backend and its detector model is on no public hw_sim branch), so this repo ships
**vendored copies of just their config types** under `vendor/` (the public "struct
database"). A plain `cargo build` uses those and needs no private/ssh access.

Maintainers with access to the private repo can check that the vendored copies still
match upstream:

```.bash
cargo update --manifest-path upstream_check/Cargo.toml -p node -p km-server -p configs
cargo check  --manifest-path upstream_check/Cargo.toml
```

The update step matters: the dependencies track a branch but the lockfile pins a
commit, so checking without it re-verifies a stale revision and passes for the
wrong reason.

A compile error there means a config field changed upstream and the vendored copies
(plus `src/config.rs`) need updating. See `vendor/README.md` and
`upstream_check/README.md`.




