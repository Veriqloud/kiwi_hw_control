use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct AliceIpcConfig {
    pub command_path: String,
    pub angle_file_path: String,
    pub gc_read_file_path: String,
    pub hw_params_file_path: String,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct BobIpcConfig {
    pub command_path: String,
    pub angle_file_path: String,
    pub gcr_file_path: String,
    pub gc_read_file_path: String,
    pub hw_params_file_path: String,
}

impl Default for AliceIpcConfig {
    fn default() -> Self {
        AliceIpcConfig {
            command_path: "/tmp/fpga_alice".to_string(),
            angle_file_path: "/tmp/gc_alice_angle.fifo".to_string(),
            gc_read_file_path: "/tmp/gc_alice_gc.fifo".to_string(),
            hw_params_file_path: "/tmp/hw_params_alice.fifo".to_string(),
        }
    }
}

impl Default for BobIpcConfig {
    fn default() -> Self {
        BobIpcConfig {
            command_path: "/tmp/fpga_bob".to_string(),
            angle_file_path: "/tmp/gc_bob_angle.fifo".to_string(),
            gcr_file_path: "/tmp/gc_bob_gcr.fifo".to_string(),
            gc_read_file_path: "/tmp/gc_bob_gc.fifo".to_string(),
            hw_params_file_path: "/tmp/hw_params_bob.fifo".to_string(),
        }
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
#[serde(untagged)]
pub enum Configuration {
    Bob(BobIpcConfig),
    Alice(AliceIpcConfig),
}

impl Default for Configuration {
    fn default() -> Self {
        Configuration::Bob(BobIpcConfig::default())
    }
}
