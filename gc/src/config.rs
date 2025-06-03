use core::panic;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct Configuration {
    pub player: QlinePlayer,
    pub fiber_delay: u32,
}

impl Configuration {
    pub fn from_pathbuf_alice(path: &PathBuf) -> Self {
        let contents = std::fs::read_to_string(path)
            .expect(&format!("failed reading config at path: {path:?}"));

        let conf: Configuration =
            serde_json::from_str(&contents).expect(&format!("failed to parse config: {contents}"));

        match &conf.player {
            QlinePlayer::Alice { .. } => conf,
            QlinePlayer::Bob { .. } => {
                panic!("you're building Alice with the wrong config! This config is for Bob")
            }
            QlinePlayer::Charlie { .. } => {
                panic!("you're building Alice with the wrong config! This config is for a Charlie")
            }
        }
    }

    pub fn from_pathbuf_bob(path: &PathBuf) -> Self {
        let contents = std::fs::read_to_string(path)
            .expect(&format!("failed reading config at path: {path:?}"));

        let conf: Configuration =
            serde_json::from_str(&contents).expect(&format!("failed to parse config: {contents}"));

        match &conf.player {
            QlinePlayer::Bob { .. } => conf,
            QlinePlayer::Alice { .. } => {
                panic!("you're building Bob with the wrong config! This config is for Alice")
            }
            QlinePlayer::Charlie { .. } => {
                panic!("you're building Bob with the wrong config! This config is for a Charlie")
            }
        }
    }

    pub fn alice_config(&self) -> AliceConfig {
        match &self.player {
            QlinePlayer::Alice(alice_config) => alice_config.to_owned(),
            QlinePlayer::Bob(_) | QlinePlayer::Charlie(_) => unreachable!(),
        }
    }

    pub fn bob_config(&self) -> BobConfig {
        match &self.player {
            QlinePlayer::Bob(bob_config) => bob_config.to_owned(),
            QlinePlayer::Alice(_) | QlinePlayer::Charlie(_) => unreachable!(),
        }
    }

    pub fn charlie_config(&self) -> CharlieConfig {
        match &self.player {
            QlinePlayer::Charlie(charlie_config) => charlie_config.to_owned(),
            QlinePlayer::Alice(_) | QlinePlayer::Bob(_) => unreachable!(),
        }
    }
}

#[derive(Debug, Deserialize, Serialize)]
pub enum QlinePlayer {
    Alice(AliceConfig),
    Bob(BobConfig),
    Charlie(CharlieConfig),
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct AliceConfig {
    pub fifo: ConfigFifoAlice,
    pub network: ConfigNetworkAlice,
    pub decoy_delay: u32,
}

#[derive(Debug, Deserialize, Serialize, Default, Clone)]
pub struct ConfigFifoAlice {
    #[serde(default = "ConfigFifoAlice::default_command_socket_path")]
    pub command_socket_path: String,
    #[serde(default = "ConfigFifoAlice::default_gc_file_path")]
    pub gc_file_path: String,
    #[serde(default = "ConfigFifoAlice::default_angle_file_path")]
    pub angle_file_path: String,
}

impl ConfigFifoAlice {
    fn default_command_socket_path() -> String {
        "/home/vq-user/qline/startstop.s".to_string()
    }

    fn default_gc_file_path() -> String {
        "/dev/xdma0_h2c_0".to_string()
    }

    fn default_angle_file_path() -> String {
        "/dev/xdma0_c2h_3".to_string()
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ConfigNetworkAlice {
    pub ip_bob_gc: String,
    pub ip_bob_qber: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct BobConfig {
    pub fifo: ConfigFifoBob,
}

#[derive(Debug, Deserialize, Serialize, Default, Clone)]
pub struct ConfigFifoBob {
    #[serde(default = "ConfigFifoBob::default_angle_file_path")]
    pub angle_file_path: String,
    #[serde(default = "ConfigFifoBob::default_gcr_file_path")]
    pub gcr_file_path: String,
    #[serde(default = "ConfigFifoBob::default_gc_file_path")]
    pub gc_file_path: String,
    #[serde(default = "ConfigFifoBob::default_click_result_file_path")]
    pub click_result_file_path: String,
}

impl ConfigFifoBob {
    fn default_angle_file_path() -> String {
        "/dev/xdma0_c2h_3".to_string()
    }

    fn default_gcr_file_path() -> String {
        "/dev/xdma0_c2h_1".to_string()
    }

    fn default_gc_file_path() -> String {
        "/dev/xdma0_h2c_0".to_string()
    }

    fn default_click_result_file_path() -> String {
        "/home/vq-user/qline/result.f".to_string()
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct CharlieConfig {}

#[cfg(test)]
mod test {
    use crate::config::{BobConfig, CharlieConfig, ConfigFifoBob};

    use super::Configuration;

    #[test]
    fn print_alice_config() {
        let conf = Configuration {
            player: super::QlinePlayer::Alice(super::AliceConfig {
                fifo: super::ConfigFifoAlice {
                    command_socket_path: "command socket path".to_string(),
                    gc_file_path: "gc file path".to_string(),
                    angle_file_path: "angle file path".to_string(),
                },
                network: super::ConfigNetworkAlice {
                    ip_bob_gc: "ip bob gc".to_string(),
                    ip_bob_qber: "ip bob qber".to_string(),
                },
                decoy_delay: 42,
            }),
            fiber_delay: 420,
        };

        println!("{}", serde_json::to_string_pretty(&conf).unwrap());
    }

    #[test]
    fn print_bob_config() {
        let conf = Configuration {
            player: super::QlinePlayer::Bob(BobConfig {
                fifo: ConfigFifoBob {
                    angle_file_path: "angle_file_path".to_string(),
                    gcr_file_path: "gcr_file_path".to_string(),
                    gc_file_path: "gc_file_path".to_string(),
                    click_result_file_path: "click_result_file_path".to_string(),
                },
            }),
            fiber_delay: 42,
        };

        println!("{}", serde_json::to_string_pretty(&conf).unwrap());
    }

    #[test]
    fn print_charlie_config() {
        let conf = Configuration {
            player: super::QlinePlayer::Charlie(CharlieConfig {}),
            fiber_delay: 42,
        };

        println!("{}", serde_json::to_string_pretty(&conf).unwrap());
    }
}
