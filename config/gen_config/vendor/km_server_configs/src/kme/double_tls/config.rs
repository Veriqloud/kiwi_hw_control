use std::{net::Ipv4Addr, sync::Arc};

use base64::{engine::general_purpose, Engine};
use serde::{Deserialize, Deserializer, Serialize};

use crate::configuration::{BindAddress, KmeID};

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct WritePort(pub u16);

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct ReadPort(pub u16);

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct Configuration {
    pub peers: Vec<Peer>,
    /// Port where incoming connections will be written to
    pub write_port: WritePort,
    /// Port where incoming connections will be read from
    pub read_port: ReadPort,

    /// This field is skipped because it comes from the main configuration file
    #[serde(skip_deserializing)]
    pub bind_address: Arc<BindAddress>,

    /// This field is skipped because it comes from the main configuration file
    #[serde(skip_deserializing)]
    pub kme_id: Arc<KmeID>,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct Peer {
    /// Identifying name
    pub name: String,
    /// Just the address, no port number
    pub address: Ipv4Addr,
    /// Port where we can write to the peer
    pub write_port: u16,
    /// Port to connect to so we can read the peer's messages
    pub read_port: u16,
    /// SAEs linked to the KMS peer
    pub sae_ids: Vec<String>,
    /// Key for a given pair of KMS
    pub psk: PSK,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct PSK {
    pub id: String,

    #[serde(deserialize_with = "base64_psk")]
    pub value: Vec<u8>,
}

/// TODO: Use this: https://docs.serde.rs/serde/de/trait.Error.html  to return an error instead of the unwrap here
fn base64_psk<'de, D>(deserializer: D) -> Result<Vec<u8>, D::Error>
where
    D: Deserializer<'de>,
{
    let psk = String::deserialize(deserializer)?;
    let base64_key = general_purpose::STANDARD.decode(psk).unwrap();
    Ok(base64_key)
}
