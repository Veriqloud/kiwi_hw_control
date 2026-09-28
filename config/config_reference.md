---
title: "Qline configuration reference"
subtitle: "meta_config.json and sim_config.json"
---

`gen_config` turns one `meta_config.json` into the configuration of every program of
a Qline pair. For the simulator it also reads `sim_config.json`. It writes into the
current directory:

| File | Program |
|---|---|
| `alice/gc.json`, `bob/gc.json` | gc (global counter) |
| `alice/qber.json`, `bob/qber.json` | qber |
| `alice/node.json`, `bob/node.json` | node (postprocessing) |
| `alice/kms.json`, `bob/kms.json` | km-server (KMS, ETSI GS QKD 014 API) |
| `alice/network.json`, `bob/network.json` | the Python hardware tooling in `remote/` and `local/` |
| `alice/sim.json`, `bob/sim.json` | hw_sim (simulator only) |

```bash
gen_config -c meta_config.json                        # real hardware
gen_config -c meta_config.json -s sim_config.json     # simulator
gen_config                                            # simulator, built-in defaults
gen_config -c meta_config.json -g                     # also generate the mTLS certificates
```

**Simulator mode** (`-s`, or no arguments) differs from hardware mode in three ways:

- Alice and Bob run on one machine, so some paths get a `_alice` or `_bob` suffix to
  keep them apart. The tables below mark these fields with *suffixed*.
- The node keys at `node.key_path` are generated with `openssl` when they are missing,
  and `kms.alice_peer_id` and `kms.bob_peer_id` are derived from them. The values in
  the meta config are ignored.
- gc ignores the gcr timeout.

# meta_config.json

## ip

| Field | Sim value | Meaning |
|---|---|---|
| `alice` | `127.0.0.1` | Alice's address on the client-side network. Alice's KMS serves its ETSI 014 API here (`api_addr` in `kms.json`), the `local/etsi14` scripts connect here, and it is a SAN of Alice's KMS certificate. |
| `bob` | `127.0.0.1` | The same for Bob. |
| `alice_wrs` | `127.0.0.1` | Alice's address on the Alice–Bob link through the White Rabbit switch. Alice's node listens here on `port.node_alice` and is the libp2p boot node Bob dials. The `bind_address` in `kms.json` is this address's /24 network (last octet 0); the KMS does not use it. |
| `bob_wrs` | `127.0.0.1` | Bob's address on the link. gc and qber on both sides connect to Bob here (`port.gc`, `port.qber`), and Bob's node announces `bob_wrs:port.node_bob`. |

## port

| Field | Sim value | Used by |
|---|---|---|
| `hw` | 13000 | `remote/hw_*.py`, the hardware interface server. Hardware only. |
| `hws` | 13001 | `remote/hws_*.py`, the hardware server that runs calibration and coordinates Alice and Bob. Hardware only. |
| `mon` | 13002 | `remote/mon_*.py`, the monitoring server. Hardware only. |
| `kms_alice` | 13003 | Alice's ETSI GS QKD 014 API. |
| `kms_bob` | 13004 | Bob's ETSI GS QKD 014 API. |
| `gc` | 13005 | gc: Bob listens on `bob_wrs:gc`, Alice connects. |
| `qber` | 13006 | qber: Bob listens on `bob_wrs:qber`, Alice connects. |
| `node_alice` | 13007 | Alice's node, libp2p over TCP on `alice_wrs`. |
| `node_bob` | 13008 | Bob's node, libp2p over TCP on `bob_wrs`. |
| `showlogs` | 13009 | `monitoring/server.py`, the log viewer. Hardware only. |
| `restartd` | 13010 | `remote/restartd.py`, restarts qline services over TCP. Hardware only. |
| `logd` | 13011 | `remote/logd.py`, read-only access to the log files. Hardware only. |

The hardware-only ports are only written to `network.json`.

## file

Paths of the FIFOs, sockets and files the programs exchange data through.

| Field | Sim value | Suffixed | Meaning |
|---|---|---|---|
| `gcr` | `/tmp/gcr.fifo` | no | FIFO carrying the global counter and detection result from Bob's FPGA to gc. |
| `gc` | `/tmp/gc.fifo` | yes | FIFO carrying the global counter from gc back to the FPGA. |
| `angle` | `/tmp/angle.fifo` | yes | FIFO carrying the qubit angles from the FPGA; the node and qber read it. |
| `result` | `/tmp/result.fifo` | no | FIFO carrying Bob's click results from gc to the node and qber. |
| `gcuser` | `""` | no | Optional FIFO receiving a copy of the global counter for a user program. Empty disables it. |
| `fpgareg` | `/tmp/fpgareg` | yes | FPGA control registers (memory mapped). In the simulator, hw_sim's command path. |
| `startstop` | `/tmp/gc_startstop` | yes | Unix socket for start and stop commands to gc; the node and qber send through it. |
| `hw_params` | `/tmp/hw_params.txt` | yes | Current hardware parameters, read by gc and hw_sim. |
| `kms` | `/tmp/kms.fifo` | yes | Unix socket the node delivers final keys to its KMS through. |

## kms

| Field | Sim value | Meaning |
|---|---|---|
| `alice_peer_id` | derived | libp2p peer ID of Alice's node. It names Alice's KMS (`kme_config.P2P.name`), which makes it the SAE ID Bob uses in ETSI requests, and it identifies the boot node. On hardware it must be the peer ID of the key at Alice's `node.key_path`. |
| `bob_peer_id` | derived | The same for Bob. |
| `key_lifetime_ms` | 3600000 | Time a key stays in the KMS key pool before it expires unused. |
| `default_key_size` | 512 | Size of the final keys in bits. It sets both the node's `requested_final_key_size` and the size the KMS delivers, so the two always match. |
| `max_key_count` | 100000 | Largest number of keys the KMS key pool holds. |
| `authentication` | `false` | Mutual TLS on the ETSI API (`SAEs.mtls` in `kms.json`). With `true` the API serves HTTPS and accepts only clients presenting a certificate from the configured CA with the CN `sae_id`. The certificates come from `gen_config -g`. |
| `ca_path` | `./authentication/certs/ca.crt` | Suffixed. CA certificate the KMS verifies client certificates against. |
| `cert_path` | `./authentication/certs/cert.pem` | Suffixed. The KMS's server certificate. |
| `key_path` | `./authentication/private/eckey_pkcs8.pem` | Suffixed. The KMS's private key, PKCS#8. |

The three paths are written to `kms.json` as they are, so a relative path is resolved
against the KMS's working directory. `gen_config -g` copies the generated files to
`alice/` and `bob/` under the basenames of these paths.

## node

| Field | Sim value | Meaning |
|---|---|---|
| `key_path` | `keys/node.pk8` | Suffixed. The node's libp2p identity, an RSA key in PKCS#8 DER. The peer IDs are derived from it. |
| `qtol` | 0.09 | QBER tolerance: the highest estimated QBER at which a round is still postprocessed. |
| `clicks_per_round` | 10000000 | Detection windows read from the hardware per postprocessing round, two per angle byte. Larger rounds take longer and give better finite-size statistics. |
| `key_basis_mode` | Asymmetrical, 0.9 | Which bases become key, see below. |
| `decoystates` | set | Decoy-state parameters, see below. Absent disables the decoy-state analysis. |

**key_basis_mode** is one of:

- `"Symmetrical"`, the default: both bases go into the key, and parameter estimation
  sacrifices a random sample of the sifted key.
- `{"Asymmetrical": {"expected_key_basis_probability": p}}`: only the Z basis becomes
  key and the X basis is published in full for estimation. `p` is the probability with
  which the source is expected to prepare Z. The node only checks the observed split
  against it and warns about a round that deviates. `p` is optional. It must equal
  `source_key_basis_probability` in `sim_config.json`.

**decoystates**:

| Field | Sim value | Meaning |
|---|---|---|
| `mu1` | 0.23 | Mean photon number of the signal pulses. |
| `mu2` | 0.076 | Mean photon number of the decoy pulses, lower than `mu1`. |
| `p1` | 0.55 | Probability of a pulse being signal; decoy is `1 - p1`. |
| `esec` | 1e-10 | Secrecy failure probability in the final key length bound. |
| `ecor` | 1e-10 | Correctness failure probability in the final key length bound. |
| `K` | 19 | Number of security parameters the secrecy budget is split over (Rusca one-decoy bound). |

`mu1`, `mu2` and `p1` must equal `decoy_states` in `sim_config.json`.

## tls

Only used by `gen_config -g`. The block is optional; its defaults are the values shown.

| Field | Default | Meaning |
|---|---|---|
| `country`, `state`, `locality`, `org`, `org_unit` | FR, Paris, Paris, VeriQloud, Veriqloud-KME | Subject fields of the certificates. |
| `ca_cn` | VQKME | Common name of the root CA. |
| `validity_days` | 1095 | Validity of every generated certificate. |
| `ec_curve` | secp384r1 | Elliptic curve of every generated key. |
| `extra_sans` | `[]` | SANs added to both KMS server certificates, e.g. `"DNS:kms.example.com"` or `"IP:10.0.0.5"`. |

`-g` creates one EC root CA in `certs/`. The CA signs a server certificate for each
KMS and one client certificate with the CN `sae_id`. Each server certificate carries
the SANs `IP:<ip.alice or ip.bob>`, `DNS:localhost` and `IP:127.0.0.1`, plus
`extra_sans`. The client bundle (`ca.crt`, `sae_cert.pem`, `sae_key.pem`) is written
to `client/`; the `local/etsi14` scripts read it with `--auth` from
`$KMS_CLIENT_CERTS`. Running `-g` again replaces the whole chain.

## Fixed values

These values in the generated files do not come from the meta config:

| Value | Where |
|---|---|
| SAE ID `sae_id` | the single SAE in `kms.json`, and the CN of the client certificate |
| KMS IDs `alice_kme`, `bob_kme` | `kme_id` in `kms.json` |
| `max_key_per_request` 100, `min_key_size` 128, `max_key_size` 4096 | `kms.json`; the KMS delivers `default_key_size` only |
| `static_angles` `[0, 32, 96, 64]` | `node.json` |
| ready flag `/tmp/qkd_ready`; idle flag `/tmp/node_idle` (sim: `_alice`, `_bob`) | `gc.json` |
| log level `Info` | all programs |

# sim_config.json

Both simulators read the same values; only their FIFO paths differ.

| Field | Shipped | Meaning |
|---|---|---|
| `angles` | `[0, 32, 96, 64]` | Angle codes the source prepares, as the hardware writes them: 0 and 64 are the Z basis, 32 and 96 the X basis. Keep as shipped. |
| `seed` | 42 | Seed of the random stream both simulators share. The stream restarts at every session start, so two runs see identical photon data. |
| `eta` | 0.01 | Single-photon transmission of the channel. |
| `qberr` | 0.02 | Optical error rate: a number, or `{"type": "Fixed", "value": v}`, `{"type": "Uniform", "min": a, "max": b}` or `{"type": "Gaussian", "mean": m, "std_dev": s}`, redrawn for every batch. |
| `pulse_distance` | 12.5e-9 | Time between pulses in seconds; 12.5 ns is 80 MHz. |
| `dead_time` | 15e-6 | Detector dead time in seconds: no click follows another within it, which caps the count rate at `1/dead_time`. 0 disables it. |
| `dark_count_probability` | 1.25e-6 | Dark-count probability per gate. A dark count rate D in counts per second is `D · pulse_distance`; 1.25e-6 is 100 cps at 12.5 ns. 0 disables it. |
| `afterpulse` | two components | Afterpulse model, at most two `{tau, p_ap}` components: `tau` is the detrapping time constant in seconds, `p_ap` the afterpulses per avalanche at zero hold-off, which can exceed 1. The dead time reduces it to `p_ap · e^(−dead_time/tau)`. The shipped values are the measured AUREA InGaAs SPAD. Empty disables afterpulsing. |
| `software_filter` | 0.25 | Fraction of the hardware gate the software gate keeps. Photon clicks are all kept; dark counts and afterpulses only with this probability. 1.0 disables filtering. |
| `speedup` | 10.0 | Speed relative to real time. 10 delivers ten seconds of hardware output per second; the data is identical to a real-time run with the same seed. |
| `source_key_basis_probability` | 0.9 | Probability of the source preparing the Z basis, for the asymmetric protocol; the detector is biased to `1 - p`. Absent draws all four angles uniformly. Must equal the node's `expected_key_basis_probability`. |
| `decoy_states` | `mu1` 0.23, `mu2` 0.076, `p1` 0.55 | Source intensities. Absent makes the source emit single photons. Must equal the node's `decoystates`. |

## Checks

`gen_config` compares the two files where they describe the same thing:

- `decoy_states` and `node.decoystates` with different `mu1`, `mu2` or `p1`: error.
  Set on one side only: warning.
- `source_key_basis_probability` and `expected_key_basis_probability` differing:
  error. Set on one side only: warning.

# Docker image

The simulator stack image `ghcr.io/blindqlouder/qline-stack` runs `gen_config -c
meta_config.json -s sim_config.json` at every start on a directory mounted at
`/config`, and writes `alice/`, `bob/` and `keys/` into it. On top of `gen_config`:

- The derived peer IDs are written back into `kms.alice_peer_id` and
  `kms.bob_peer_id`, so the directory works as `QLINE_CONFIG_DIR` for `local/etsi14`.
- The node keys persist in `keys/`, so the peer IDs stay the same across restarts.
- With `kms.authentication` true, the first start runs `-g`, and `kms.json` is
  pointed at the certificates in `alice/` and `bob/`. The chain is kept until
  `client/` is deleted.
- `ip.*` must stay `127.0.0.1`, since the whole pair runs in one container. Publish
  `port.kms_alice` and `port.kms_bob` with `-p`.
