# upstream_check — maintainer-only drift check

This is **not** part of `gen_config`'s normal build. It exists to catch changes in the
`node` / `km-server` (kms) / hw_sim `configs` structs — all three live in the private
qline_backend repo — that the vendored copies in `../vendor` need to track.

It reuses `../src/lib.rs` but enables the `upstream` feature, which makes `lib.rs`
alias `node` / `km_server_configs` / `simulator_configs` to the **real** crates instead
of the vendored copies. Compiling it recompiles the exact same construction code in
`../src/config.rs` against the real structs.

The git dependencies point at the remote and branch the vendored copies track:
`BlindQlouder/qline_backend`, branch `decoy`.

## Run it

Requires an ssh key with access to the private qline_backend repo:

```bash
cargo update --manifest-path upstream_check/Cargo.toml -p node -p km-server -p configs
cargo check  --manifest-path upstream_check/Cargo.toml
```

**Always update first.** The git dependencies track a *branch*, but
`upstream_check/Cargo.lock` pins the exact commit that was resolved the last time the
check ran. Without the update step cargo happily re-checks against that stale commit
and reports success while upstream has moved on — the check then tells you nothing,
which is worse than not running it. (`node_kms_models` comes along with the three named
packages; they all live in the same repo.)

If your default github.com key is not that key, cargo cannot authenticate — and it
ignores `~/.ssh/config` Host aliases, so pointing the URLs at an alias host only works
together with the git CLI transport. Both commands then need it:

```bash
export GIT_SSH_COMMAND='ssh -i ~/.ssh/<key> -o IdentitiesOnly=yes'
cargo update --config net.git-fetch-with-cli=true --manifest-path upstream_check/Cargo.toml \
  -p node -p km-server -p configs
cargo check  --config net.git-fetch-with-cli=true --manifest-path upstream_check/Cargo.toml
```

- **Compiles cleanly** → the vendored copies are still compatible with upstream.
- **Fails to compile** → a config field changed upstream. Typical errors:
  - `missing field X in initializer of Configuration` — upstream added a field.
  - `struct has no field named X` / `no variant named X` — upstream removed/renamed one.

  Port the change into the matching file under `../vendor`, adapt `../src/config.rs`
  if the generated JSON needs to change, then re-run until it compiles.

## The `comm` dependency (avoiding a lockfile collision)

`comm` lives in **this** repo and is pulled in twice during the check:

- this repo's `gc` and `qber` depend on it via the relative path `../comm`, and
- the real `node` crate depends on it too.

Both must resolve to the **same** `comm` directory. If they don't, Cargo fails with:

    error: package collision in the lockfile: packages comm v0.1.0 (<path A>) and
    comm v0.1.0 (<path B>) are different, ...

That happens when node's manifest hardcodes an absolute path to `comm` (e.g.
`/home/ai/kiwi_hw_control/comm`) that differs from where this repo is cloned (so
`gc`/`qber`'s `../comm` points somewhere else). Cargo cannot override a *path*
dependency — neither `[patch]` nor a `paths` override fixes this — so the fix must be
in **node's** `Cargo.toml`.

Make node reference `comm` via its committed git URL (not a hardcoded absolute path):

    comm = { git = "ssh://git@github.com/Veriqloud/kiwi_hw_control.git", branch = "master" }

The `[patch]` in this manifest then redirects that git `comm` to this repo's local
`comm` (the same one `gc`/`qber` use), so the whole graph resolves to a single `comm`
regardless of clone location. (A node-side relative path like
`../../kiwi_hw_control/comm` also works if you keep `kiwi_hw_control` and the node repo
as siblings, in which case the `[patch]` is simply unused.)

## Notes

- The hw_sim `configs` crate sits in a **nested** cargo workspace inside qline_backend
  (`qline_backend/hw_sim/configs`, excluded from the top-level workspace). A git
  dependency finds it by package name — cargo scans the whole checkout for manifests —
  so no subdirectory needs to be named in `Cargo.toml`.
- The check only fails on fields `../src/config.rs` *constructs*. The hw_sim
  `backend_config` block is parsed from `sim_config.json` and re-serialized rather than
  constructed, so a new backend field with a serde default passes silently; add it to
  `sim_config.json` by hand (see `../vendor/README.md`).
- The private repo paths live here (not in `../Cargo.toml`) on purpose: Cargo resolves
  optional path dependencies even when their feature is off, so putting them in the
  main manifest would break the self-contained default build for anyone without the
  private repos.
- Keep the shared (public) dependencies in `Cargo.toml` in sync with `../Cargo.toml`.
- The `time = "=0.3.36"` pin works around a `cookie`/`time` incompatibility in
  km-server's web dependency tree; it only affects this check.
- This check builds the library only (it does not include `src/main.rs`), which is
  enough to compile the config-generation code.
