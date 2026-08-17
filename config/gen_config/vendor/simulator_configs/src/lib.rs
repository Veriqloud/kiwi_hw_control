//! Vendored config types from qline_backend/hw_sim (package `configs`).
//!
//! Faithful copy of the simulator's serializable configuration types. Only the
//! serialization surface is reproduced: struct/enum definitions, field names,
//! types and `#[serde(...)]` attributes are kept verbatim so the generated JSON
//! is identical to what the real configs crate would produce. Schema derives,
//! FIFO/mmio setup code, error types and tests from upstream are omitted.
//!
//! Keep in sync with upstream; the `upstream_check` manifest compiles the same
//! construction code against the real crate and catches any drift.

pub mod backend;
pub mod ipc;

use serde::{Deserialize, Serialize};

#[derive(Debug, Default, Deserialize, Serialize, PartialEq, Clone)]
pub struct Configuration {
    pub backend_config: backend::Configuration,
    pub ipc_config: ipc::Configuration,
    pub log_level: LogLevel,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct LogLevel(pub String);

impl Default for LogLevel {
    fn default() -> Self {
        LogLevel("Info".to_string())
    }
}
