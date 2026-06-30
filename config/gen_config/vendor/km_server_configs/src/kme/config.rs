use serde::{Deserialize, Serialize};

#[derive(PartialEq, Debug, Deserialize, Serialize, Clone)]
pub struct Configuration {
    #[serde(flatten)]
    pub cfg_type: ConfigType,
}

#[derive(PartialEq, Debug, Deserialize, Serialize, Clone)]
pub enum ConfigType {
    P2P(super::p2p::config::Configuration),
    DoubleTLS(super::double_tls::config::Configuration),
    ThirdPartyDiscovery(super::third_party_discovery::config::Configuration),
}

impl Default for Configuration {
    fn default() -> Self {
        Self {
            cfg_type: ConfigType::P2P(super::p2p::config::Configuration::default()),
        }
    }
}
