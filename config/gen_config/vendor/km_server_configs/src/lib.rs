//! Vendored config types from qline_backend/kms (library `km_server_configs`).
//!
//! Faithful copy of the kms crate's serializable configuration tree. Only the
//! serialization surface is reproduced; schema/error derives, runtime impls and
//! tests from upstream are intentionally omitted. Module paths mirror upstream so
//! gen_config's `km_server_configs::...` references resolve unchanged.
//!
//! Keep in sync with upstream; `gen_config --features upstream` compiles the same
//! construction code against the real km-server crate and catches any drift.

pub mod configuration;
pub mod ipc;
pub mod kme;
pub mod sae_api;
pub mod storage;

pub use configuration::{BindAddress, Configuration, KmeID, LogLevel};
