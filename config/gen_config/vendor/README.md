# vendor/ — the public "struct database"

`gen_config` builds the per-program config files (node, kms, gc, qber, sim, network)
by constructing the *real* config structs of each program and serializing them to
JSON. Constructing those structs with exhaustive struct literals is also how we catch
upstream changes: if a program adds/removes/renames a config field, `gen_config`
stops compiling until the generation code is adapted.

For `gc`, `qber` and `simulator_configs` (hw_sim, a public repo) we depend on the real
crates directly. But `node` and `km-server` (kms) live in **private** repos, and this
repo is open source. To keep the default build self-contained — buildable by anyone,
with no private/ssh dependencies — this directory holds **vendored copies of just the
config types** of those two crates:

- `vendor/node/` — package `node-vendored`, mirrors the config types from
  `qline_backend/node/src/lib.rs`.
- `vendor/km_server_configs/` — package `km-server-vendored`, library
  `km_server_configs`, mirrors the kms config module tree
  (`configuration`, `kme`, `storage`, `sae_api`, `ipc`).

These are faithful to the **serialization surface only**: struct/enum definitions,
field names, types and `#[serde(...)]` attributes are kept so the generated JSON is
byte-identical to what the real crates produce. Schema/Display/error derives, runtime
impls and tests from upstream are intentionally dropped.

`gen_config/src/lib.rs` aliases these crates to `node` / `km_server_configs`, so
`src/config.rs` is written against those names and is identical whether it builds
against the vendored copies (default) or the real crates (drift check).

## Two-step build

1. **Default (everyone):** `cargo build` uses the vendored copies here. No private deps.
2. **Drift check (maintainer, needs access to the private repos):**
   `cargo check --manifest-path upstream_check/Cargo.toml`
   recompiles the same `src/config.rs` against the real `node`/`km-server` crates.
   Any field added/removed/renamed upstream becomes a compile error, prompting you to
   update the vendored copies here (and the generation code in `src/config.rs`).
   See `../upstream_check/README.md`.

## Keeping the vendored copies in sync

When you bump the pinned node/kms versions:

1. Run the drift check. If it still compiles, nothing changed that affects us.
2. If it fails, port the relevant struct/field change from upstream into the matching
   file under `vendor/`, and adjust `src/config.rs` if needed.
3. Re-run both the default build and the drift check; confirm the generated JSON is
   unchanged for an unaffected config.
