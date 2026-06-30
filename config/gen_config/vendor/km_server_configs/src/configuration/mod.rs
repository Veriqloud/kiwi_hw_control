use serde::{Deserialize, Serialize};
use std::{
    net::{IpAddr, Ipv4Addr},
    sync::Arc,
};

#[derive(Debug, Deserialize, Serialize, PartialEq, Default)]
pub struct Configuration {
    pub kme_config: crate::kme::config::Configuration,
    pub storage_config: crate::storage::config::Configuration,
    pub sae_api_config: crate::sae_api::config::Configuration,
    pub ipc_config: crate::ipc::config::Configuration,
    pub bind_address: Arc<BindAddress>,
    pub kme_id: Arc<KmeID>,
    pub log_level: LogLevel,
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub struct LogLevel(String);

impl Default for LogLevel {
    fn default() -> Self {
        LogLevel("Info".to_string())
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct BindAddress(pub IpAddr);

impl Default for BindAddress {
    fn default() -> Self {
        BindAddress(IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1)))
    }
}

/// Default value for KmeID is a random 7 "char" String
#[derive(Debug, Deserialize, Serialize, PartialEq, Clone, Default)]
pub struct KmeID(pub String);
