# vendor/ — the public "struct database"

`gen_config` builds the per-program config files (node, kms, gc, qber, sim, network)
by constructing the *real* config structs of each program and serializing them to
JSON. Constructing those structs with exhaustive struct literals is also how we catch
upstream changes: if a program adds/removes/renames a config field, `gen_config`
stops compiling until the generation code is adapted.

For `gc` and `qber` we depend on the real crates directly — they live in this repo. But
`node`, `km-server` (kms) and now hw_sim's `configs` all live in the **private**
qline_backend repo, and this repo is open source. To keep the default build
self-contained — buildable by anyone, with no private/ssh dependencies — this directory
holds **vendored copies of just the config types** of those three crates:

- `vendor/node/` — package `node-vendored`, mirrors the config types from
  `qline_backend/node/src/lib.rs`.
- `vendor/km_server_configs/` — package `km-server-vendored`, library
  `km_server_configs`, mirrors the kms config module tree
  (`configuration`, `kme`, `storage`, `sae_api`, `ipc`).
- `vendor/simulator_configs/` — package `simulator-configs-vendored`, mirrors
  hw_sim's `configs` crate (`backend`, `ipc` and the top-level `Configuration`).

hw_sim is a public project, so this last one used to be a plain git dependency on
`Veriqloud/hw_sim`. It is vendored because hw_sim's authoritative copy now lives inside
qline_backend (see `qline_backend/hw_sim/README.md`) and the detector model it grew
there — `dead_time`, `dark_count_probability`, `afterpulse`, `software_filter`,
`speedup` — is on no public hw_sim branch. Since serde ignores unknown fields, building
against public master would not fail: it would silently *drop* every one of those
fields while round-tripping `sim_config.json` into the generated `sim.json`. **When the
detector-model commits land in public `Veriqloud/hw_sim`, delete this copy and restore
the git dependency** (the line is kept, commented out, in `../Cargo.toml`).

These are faithful to the **serialization surface only**: struct/enum definitions,
field names, types and `#[serde(...)]` attributes are kept so the generated JSON is
byte-identical to what the real crates produce. Schema/Display/error derives, runtime
impls (hw_sim's FIFO and mock-mmio setup, for instance) and tests from upstream are
intentionally dropped.

`gen_config/src/lib.rs` aliases these crates to `node` / `km_server_configs` /
`simulator_configs`, so `src/config.rs` is written against those names and is identical
whether it builds against the vendored copies (default) or the real crates (drift
check).

## Two-step build

1. **Default (everyone):** `cargo build` uses the vendored copies here. No private deps.
2. **Drift check (maintainer, needs access to the private repo):**
   `cargo update --manifest-path upstream_check/Cargo.toml -p node -p km-server -p configs`
   followed by `cargo check --manifest-path upstream_check/Cargo.toml`
   recompiles the same `src/config.rs` against the real `node` / `km-server` /
   `configs` crates. Any field added/removed/renamed upstream becomes a compile error,
   prompting you to update the vendored copies here (and the generation code in
   `src/config.rs`). The update step is not optional: the lockfile pins a commit, so
   without it the check passes against whatever upstream looked like last time.
   See `../upstream_check/README.md`.

## Keeping the vendored copies in sync

When you bump the pinned node/kms/hw_sim versions:

1. Run the drift check. If it still compiles, nothing changed that affects us.
2. If it fails, port the relevant struct/field change from upstream into the matching
   file under `vendor/`, and adjust `src/config.rs` if needed.
3. Re-run both the default build and the drift check; confirm the generated JSON is
   unchanged for an unaffected config.

One blind spot to watch: the drift check only fails on fields `src/config.rs`
*constructs*. The hw_sim `backend_config` block is not constructed — it is parsed out of
`sim_config.json` and re-serialized — so a new backend field with a `#[serde(default)]`
compiles fine here and silently takes its default. After porting a hw_sim change, add
the new field to `sim_config.json` (and to `config/sim/sim_config.json`) explicitly and
document it in `../README.md`.
