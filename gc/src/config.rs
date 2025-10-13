use core::panic;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub struct Configuration {
    pub player: QlinePlayer,
    pub current_hw_parameters_file_path: String,
    #[serde(default = "Configuration::default_fpga_start_socket_path")]
    pub fpga_start_socket_path: String,
    #[serde(default = "Configuration::default_log_level")]
    pub log_level: String,
}

impl Configuration {
    pub fn save_to_file(self, path: &PathBuf){
        let s = serde_json::to_string_pretty(&self).unwrap();
        std::fs::write(path, s).expect("writing config to file");
    }
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

    fn default_fpga_start_socket_path() -> String {
        "/dev/xdma0_user".to_string()
    }

    fn default_log_level() -> String {
        "INFO".to_string()
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub enum QlinePlayer {
    Alice(AliceConfig),
    Bob(BobConfig),
    Charlie(CharlieConfig),
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
pub struct AliceConfig {
    pub fifo: ConfigFifoAlice,
    pub network: ConfigNetwork,
}

#[derive(Debug, Deserialize, Serialize, Default, Clone, PartialEq)]
pub struct ConfigFifoAlice {
    #[serde(default = "ConfigFifoAlice::default_command_socket_path")]
    pub command_socket_path: String,
    #[serde(default = "ConfigFifoAlice::default_gc_file_path")]
    pub gc_file_path: String,
}

impl ConfigFifoAlice {
    fn default_command_socket_path() -> String {
        "/home/vq-user/qline/startstop.s".to_string()
    }

    fn default_gc_file_path() -> String {
        "/dev/xdma0_h2c_0".to_string()
    }
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
pub struct ConfigNetwork {
    pub ip_gc: String,
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
pub struct BobConfig {
    pub fifo: ConfigFifoBob,
    pub network: ConfigNetwork,
}

#[derive(Debug, Deserialize, Serialize, Default, Clone, PartialEq)]
pub struct ConfigFifoBob {
    #[serde(default = "ConfigFifoBob::default_gcr_file_path")]
    pub gcr_file_path: String,
    #[serde(default = "ConfigFifoBob::default_gc_file_path")]
    pub gc_file_path: String,
    #[serde(default = "ConfigFifoBob::default_click_result_file_path")]
    pub click_result_file_path: String,
    #[serde(default = "ConfigFifoBob::default_gcuser_file_path")]
    pub gcuser_file_path: String,
}

impl ConfigFifoBob {
    fn default_gcr_file_path() -> String {
        "/dev/xdma0_c2h_1".to_string()
    }

    fn default_gc_file_path() -> String {
        "/dev/xdma0_h2c_0".to_string()
    }

    fn default_click_result_file_path() -> String {
        "/home/vq-user/qline/result.f".to_string()
    }
    fn default_gcuser_file_path() -> String {
        "".to_string()
    }
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq)]
pub struct CharlieConfig {}

#[cfg(test)]
mod test {

    use super::{
        AliceConfig, BobConfig, CharlieConfig, ConfigFifoAlice, ConfigFifoBob, ConfigNetwork,
        Configuration, QlinePlayer,
    };

    #[test]
    fn test_alice_config_parsing() {
        let path = std::path::PathBuf::from("../config/sim/local_sim_gc_alice.json");
        let conf_from_file = Configuration::from_pathbuf_alice(&path);

        let hardcoded_conf = Configuration {
            player: QlinePlayer::Alice(AliceConfig {
                network: ConfigNetwork {
                    ip_gc: "localhost:50051".to_string(),
                },
                fifo: ConfigFifoAlice {
                    command_socket_path: "/tmp/gc_alice_command.socket".to_string(),
                    gc_file_path: "/tmp/gc_alice_gc.fifo".to_string(),
                },
            }),
            current_hw_parameters_file_path: "../config/alice_hw_params.txt".to_string(),
            fpga_start_socket_path: "/tmp/fpga_alice".to_string(),
            log_level: "INFO".to_string(),
        };

        assert_eq!(conf_from_file, hardcoded_conf);

        println!(
            "{}",
            serde_json::to_string_pretty(&conf_from_file).unwrap()
        );
    }

    #[test]
    fn test_bob_config_parsing() {
        let path = std::path::PathBuf::from("../config/sim/local_sim_gc_bob.json");
        let conf_from_file = Configuration::from_pathbuf_bob(&path);

        let hardcoded_conf = Configuration {
            player: QlinePlayer::Bob(BobConfig {
                network: ConfigNetwork {
                    ip_gc: "localhost:50051".to_string(),
                },
                fifo: ConfigFifoBob {
                    gcr_file_path: "/tmp/gc_bob_gcr.fifo".to_string(),
                    gc_file_path: "/tmp/gc_bob_gc.fifo".to_string(),
                    click_result_file_path: "/tmp/gc_bob_click_result.fifo".to_string(),
                    gcuser_file_path: "/tmp/gcuser_bob.fifo".to_string(),
                },
            }),
            current_hw_parameters_file_path: "../config/bob_hw_params.txt".to_string(),
            fpga_start_socket_path: "/tmp/fpga_bob".to_string(),
            log_level: "INFO".to_string(),
        };

        assert_eq!(conf_from_file, hardcoded_conf);

        println!(
            "{}",
            serde_json::to_string_pretty(&conf_from_file).unwrap()
        );
    }

    #[test]
    fn print_charlie_config() {
        let conf = Configuration {
            player: QlinePlayer::Charlie(CharlieConfig {}),
            current_hw_parameters_file_path: "/path/to/dyn/params/file.txt".to_string(),
            fpga_start_socket_path: Configuration::default_fpga_start_socket_path(),
            log_level: Configuration::default_log_level(),
        };

        println!("{}", serde_json::to_string_pretty(&conf).unwrap());
    }
}
