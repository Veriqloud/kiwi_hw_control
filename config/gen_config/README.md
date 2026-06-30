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




