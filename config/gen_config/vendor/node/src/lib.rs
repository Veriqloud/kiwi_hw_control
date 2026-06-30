//! Vendored config types from qline_backend/node.
//!
//! Faithful copy of node's serializable configuration types. Only the
//! serialization surface is reproduced: struct/enum definitions, field names,
//! types and `#[serde(...)]` attributes are kept verbatim so the generated JSON
//! is identical to what the real node crate would produce. Schema/Display/error
//! derives, runtime impls and tests from upstream are intentionally omitted.
//!
//! Keep in sync with upstream; `gen_config --features upstream` compiles the same
//! construction code against the real node crate and catches any drift.

use libp2p::{identity::Keypair, pnet::PreSharedKey, Multiaddr, PeerId};
use serde::{Deserialize, Deserializer, Serialize, Serializer};

pub const DEFAULT_BATCH_SIZE_ANGLES: usize = 1024;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Hash, Eq)]
pub struct PeerIdentity(pub String);

impl From<&PeerId> for PeerIdentity {
    fn from(value: &PeerId) -> Self {
        PeerIdentity(value.to_string())
    }
}

impl From<PeerId> for PeerIdentity {
    fn from(value: PeerId) -> Self {
        PeerIdentity(value.to_string())
    }
}

/// Simplified hardware type for sharing with peers - contains no local implementation details
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub enum PeerHardwareType {
    Source,
    Modulator,
    Detector,
}

/// Describes the hardware currently installed on this machine: photon source, photon modulator, photon detector.
/// Is in node config, because we don't expect the hardware to be changed while node is running.
#[derive(Serialize, Deserialize, Debug, PartialEq, Eq, Clone)]
#[serde(tag = "type")]
pub enum HardwareType {
    Source {
        command_socket_path: String,
        angles_file_path: String,
    },
    Modulator {
        angles_file_path: String,
    },
    Detector {
        angles_file_path: String,
        click_results_file_path: String,
    },
}

#[derive(Deserialize, Clone, Serialize, Debug)]
pub struct Configuration {
    pub hardware_type: HardwareType,

    /// The address that other node instances can reach us at.
    /// If using libp2p, it's expected to be a Multiaddr, for example: /ip4/127.0.0.1/tcp/62649
    #[serde(skip_serializing_if = "Option::is_none")]
    pub external_address: Option<Multiaddr>,

    /// Peers are expected to be filled in in the order they appear on the qline. This is important for sessions generation, and for the hardware simulator.
    pub peers: Vec<(PeerIdentity, PeerHardwareType)>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub log_level: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub libp2p: Option<LibP2P>,

    /// As defined in the hardware config
    pub static_angles: [u8; 4],

    /// File where to write qkd stats as a csv
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stats_file_path: Option<String>,

    /// Optional prefix for log file paths - if not provided, logs won't be written to files
    #[serde(skip_serializing_if = "Option::is_none")]
    pub log_file_path_prefix: Option<String>,

    /// Key size per round in bytes - defaults to 1048576 (1MB) if not specified
    #[serde(skip_serializing_if = "Option::is_none")]
    pub key_size_per_round: Option<usize>,

    /// QBER tolerance - maximum QBER value to accept for post processing operations
    /// Defaults to 0.09 if not specified
    #[serde(default = "default_qtol")]
    pub qtol: f64,

    /// Maximum number of rounds allowed per auto-generated session
    /// Sessions built from session requests are unaffected
    /// Defaults to 10 if not specified
    #[serde(default = "default_rounds_limit_per_session")]
    pub rounds_limit_per_session: u32,

    /// Requested size in bits for final keys sent to KMS
    /// If not specified, no specific size is requested. This is not the same as the round key size, which
    /// specifies how many bytes we want to get from the hardware before we start a post processing round.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub requested_final_key_size: Option<usize>,

    /// Hardware read buffer size - defaults to DEFAULT_BATCH_SIZE_ANGLES if not specified
    /// Must be a power of 2
    #[serde(
        default = "default_hw_read_buf_size",
        skip_serializing_if = "Option::is_none",
        deserialize_with = "deserialize_hw_read_buf_size"
    )]
    pub hw_read_buf_size: Option<usize>,

    /// Where we put the keys that are produced
    pub key_storage: StorageVariant,

    /// Path to a flag file signalling that the hardware is calibrated and ready
    /// for QKD. While this file is absent, the node stays idle and runs no
    /// sessions (it will not read angles or drive gc), avoiding the crash loop
    /// that results from running sessions against an uncalibrated system.
    /// Calibration (hws full_init/start) is responsible for creating it.
    /// Defaults to a path in /tmp, which is cleared on reboot, so a power-cycle
    /// forces re-calibration before QKD resumes.
    #[serde(default = "default_ready_flag_path")]
    pub ready_flag_path: String,

    /// Path of the "node idle" acknowledgement flag. The node raises this file
    /// once it has stopped running sessions and sent Stop to gc (i.e. gc is idle)
    /// after `ready_flag_path` disappears, and removes it again before resuming.
    /// hws full_init waits for this flag after lowering the ready flag, so it
    /// never reconfigures gc/FPGA while the node is mid-session. In /tmp like the
    /// ready flag so a power-cycle clears it.
    #[serde(default = "default_idle_flag_path")]
    pub idle_flag_path: String,
}

#[derive(Deserialize, Debug, Clone, Serialize, Default)]
pub enum StorageVariant {
    Fifo {
        path: String,
    },
    Database,
    #[default]
    Stdout,
}

/// PathedKeypair combines a libp2p keypair with its file path for proper serialization/deserialization.
/// This struct is needed for the serialization process: when serializing to JSON, only the file path
/// is written to the config file. When deserializing from JSON, the keypair is loaded from that file path.
#[derive(Debug, Clone)]
pub struct PathedKeypair {
    pub keypair: Keypair,
    pub path: String,
}

impl Serialize for PathedKeypair {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&self.path)
    }
}

impl<'de> Deserialize<'de> for PathedKeypair {
    fn deserialize<D>(deserializer: D) -> Result<PathedKeypair, D::Error>
    where
        D: Deserializer<'de>,
    {
        let path: String = Deserialize::deserialize(deserializer)?;

        let mut bytes = std::fs::read(path.as_str()).map_err(|e| {
            serde::de::Error::custom(format!("failed to read file: {}, because: {}", path, e))
        })?;

        let keypair = Keypair::rsa_from_pkcs8(&mut bytes)
            .map_err(|e| serde::de::Error::custom(format!("invalid rsa key: {}", e)))?;

        Ok(PathedKeypair { keypair, path })
    }
}

#[derive(Deserialize, Debug, Clone, Serialize)]
pub struct LibP2P {
    /// A rendez-vous point for nodes to discover each other. This should be the master node only, aka the hardware photon source node.
    pub boot_node: LibP2PBootNode,

    /// Our own keypair, read from a file. One must provide the path to said file, in the json config.
    pub pathedkeypair: PathedKeypair,

    #[serde(
        deserialize_with = "deserialize_psk",
        serialize_with = "serialize_psk",
        default,
        skip_serializing_if = "Option::is_none"
    )]
    pub pnet_key: Option<PreSharedKey>,
}

#[derive(Deserialize, Debug, Clone, Serialize)]
pub struct LibP2PBootNode {
    pub address: Multiaddr,
    pub peer_id: PeerId,
}

fn serialize_psk<S>(obj: &Option<PreSharedKey>, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    match obj {
        Some(_) => serializer.serialize_str("/path/to/your/pnet.key"),
        None => serializer.serialize_none(),
    }
}

fn default_qtol() -> f64 {
    0.09
}

fn default_ready_flag_path() -> String {
    "/tmp/qkd_ready".to_string()
}

fn default_idle_flag_path() -> String {
    "/tmp/node_idle".to_string()
}

fn default_rounds_limit_per_session() -> u32 {
    10
}

fn default_hw_read_buf_size() -> Option<usize> {
    Some(DEFAULT_BATCH_SIZE_ANGLES)
}

fn deserialize_hw_read_buf_size<'de, D>(deserializer: D) -> Result<Option<usize>, D::Error>
where
    D: Deserializer<'de>,
{
    let value: Option<usize> = Option::deserialize(deserializer)?;

    if let Some(size) = value {
        // Check if size is a power of 2: a number is a power of 2 if (n & (n - 1)) == 0 and n > 0
        if size == 0 || (size & (size - 1)) != 0 {
            return Err(serde::de::Error::custom(format!(
                "hw_read_buf_size must be a power of 2, got {}",
                size
            )));
        }
    }

    Ok(value)
}

fn deserialize_psk<'de, D>(deserializer: D) -> Result<Option<PreSharedKey>, D::Error>
where
    D: Deserializer<'de>,
{
    let path: String = Deserialize::deserialize(deserializer)?;

    let bytes = std::fs::read(path.as_str()).map_err(|e| {
        serde::de::Error::custom(format!("failed to read file : {path}, because: {e}"))
    })?;

    if bytes.len() != 32 {
        return Err(serde::de::Error::custom(
            "psk must be 32 bytes long. Check the libp2p documentation".to_string(),
        ));
    }

    let array: [u8; 32] = bytes[..].try_into().map_err(|_| {
        serde::de::Error::custom("psk must be 32 bytes long".to_string())
    })?;

    Ok(Some(PreSharedKey::new(array)))
}
