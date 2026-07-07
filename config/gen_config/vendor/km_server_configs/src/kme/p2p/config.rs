use serde::de::Error;
use std::net::Ipv4Addr;

use base64::{engine::general_purpose, Engine};
use serde::{Deserialize, Deserializer, Serialize, Serializer};

#[derive(Deserialize, Serialize, PartialEq, Debug, Clone)]
pub struct PeerIdString(pub String);

/// This type is needed when using a non-local network for all KMSes.
/// It specifies rendez-vous nodes, to which subsequents KMSes are expected to attempt to connect
/// to join the network, but also provides some sort of "PSK-like" check to prevent unauthorized users from
/// joining. Authorized users are listed in the [accepted_peers](Configuration#accepted_peers)
#[derive(Deserialize, Serialize, PartialEq, Debug, Default, Clone)]
pub struct Configuration {
    /// Type of network to use. The Local network is the default, and uses mDNS.
    #[serde(default)]
    pub network_type: NetworkNodeType,

    /// Type of authentication source to use.
    #[serde(default)]
    pub authentication: AuthenticationSource,

    /// Name of the peer (Alice, bob)
    pub name: String,
}

#[derive(Deserialize, Serialize, PartialEq, Debug, Clone, Default)]
pub enum NetworkNodeType {
    #[default]
    Local,
    RemoteClient {
        proxy_address: Ipv4Addr,
        proxy_port: u16,
        path_to_preshared_key: Option<String>,
    },
    RemoteServer {
        proxy_port: u16,
        path_to_preshared_key: Option<String>,
    },
}

/// Type of authentication source to use.
/// The private key to authenticate yourself on the network can be:
/// - in the config file
/// - in a Hashicorp Vault
/// - generated at startup
/// but only one of these options at a time.
#[derive(PartialEq, Debug, Clone, Serialize, Deserialize, Default)]
pub enum AuthenticationSource {
    /// This is to be used when writing the private key directly in the config makes sense (eg: almost never)
    RawPK(PKBytes),
    /// This option takes a vault token as an argument and enables calls to the API to get the actual private key from the vault.
    VaultPK(String),
    /// To be used in local mode, when we just want to "get it running" and generate keys at kms startup.
    #[default]
    AutoGen,
}

#[derive(Debug, PartialEq, Clone)]
pub struct PKBytes(pub Vec<u8>);

impl<'de> Deserialize<'de> for PKBytes {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s: &str = Deserialize::deserialize(deserializer)?;
        Ok(PKBytes(
            general_purpose::STANDARD
                .decode(s)
                .map_err(D::Error::custom)?,
        ))
    }
}

impl serde::Serialize for PKBytes {
    fn serialize<S>(&self, s: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let encoded = general_purpose::STANDARD.encode(self.0.clone());
        encoded.serialize(s)
    }
}
