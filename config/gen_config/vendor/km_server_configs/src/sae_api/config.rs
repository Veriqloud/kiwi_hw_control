use std::net::Ipv4Addr;

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct Configuration {
    // These fields are related to the ETSI specification
    pub api_addr: Ipv4Addr,
    pub api_port: u16,
    pub kme_id: String,
    pub default_key_size: u64,
    pub max_key_count: u64,
    pub max_key_per_request: u64,
    pub max_key_size: u64,
    pub min_key_size: u64,

    // This groups information on what SAEs are linked to this KME
    #[serde(rename = "SAEs")]
    pub saes: SAES,
}

impl Default for Configuration {
    fn default() -> Self {
        Self {
            // See here for the default api port explanation: https://www.ibm.com/docs/en/was/8.5.5?topic=cps-port-number-settings
            api_addr: Ipv4Addr::new(127, 0, 0, 1),
            api_port: 49152,
            kme_id: "default_id".to_string(),
            default_key_size: 512,
            max_key_count: 3000,
            max_key_per_request: 200,
            max_key_size: 2048,
            min_key_size: 512,
            saes: SAES::default(),
        }
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone, Default)]
pub struct SAES {
    pub saes: Vec<SAE>,
    pub mtls: bool,
    pub ca_certificate_path: String,
    pub server_cert_path: String,
    pub server_key_path: String,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct SAE {
    pub id: String,
}
