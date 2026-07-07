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

`gen_config` builds the config structs of each program and serializes them. `node` and
`km-server` (kms) live in private repos, so this repo ships **vendored copies of just
their config types** under `vendor/` (the public "struct database"). A plain
`cargo build` uses those and needs no private/ssh access.

Maintainers with access to the private repos can check that the vendored copies still
match upstream:

```.bash
cargo check --manifest-path upstream_check/Cargo.toml
```

A compile error there means a config field changed upstream and the vendored copies
(plus `src/config.rs`) need updating. See `vendor/README.md` and
`upstream_check/README.md`.




