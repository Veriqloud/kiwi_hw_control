# upstream_check — maintainer-only drift check

This is **not** part of `gen_config`'s normal build. It exists to catch changes in the
private `node` / `km-server` (kms) config structs that the vendored copies in
`../vendor` need to track.

It reuses `../src/lib.rs` but enables the `upstream` feature, which makes `lib.rs`
alias `node` / `km_server_configs` to the **real** private crates instead of the
vendored copies. Compiling it recompiles the exact same construction code in
`../src/config.rs` against the real structs.

## Run it

Requires access to the private node/kms repos (paths are set in `Cargo.toml`):

```bash
cargo check --manifest-path upstream_check/Cargo.toml
```

- **Compiles cleanly** → the vendored copies are still compatible with upstream.
- **Fails to compile** → a config field changed upstream. Typical errors:
  - `missing field X in initializer of Configuration` — upstream added a field.
  - `struct has no field named X` / `no variant named X` — upstream removed/renamed one.

  Port the change into the matching file under `../vendor`, adapt `../src/config.rs`
  if the generated JSON needs to change, then re-run until it compiles.

## Notes

- The private repo paths live here (not in `../Cargo.toml`) on purpose: Cargo resolves
  optional path dependencies even when their feature is off, so putting them in the
  main manifest would break the self-contained default build for anyone without the
  private repos.
- Keep the shared (public) dependencies in `Cargo.toml` in sync with `../Cargo.toml`.
- The `time = "=0.3.36"` pin works around a `cookie`/`time` incompatibility in
  km-server's web dependency tree; it only affects this check.
- This check builds the library only (it does not include `src/main.rs`), which is
  enough to compile the config-generation code.
