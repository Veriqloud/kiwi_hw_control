// Select which backend config types `config.rs` builds against. Default: the
// vendored copies in ./vendor (public, self-contained). With `--features upstream`:
// the real private node/kms crates, so drift is caught at compile time.
#[cfg(not(feature = "upstream"))]
extern crate node_vendored as node;
#[cfg(feature = "upstream")]
extern crate node_upstream as node;

#[cfg(not(feature = "upstream"))]
extern crate km_server_vendored as km_server_configs;
#[cfg(feature = "upstream")]
extern crate km_server_upstream as km_server_configs;

pub mod config;



















