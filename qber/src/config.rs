use serde::{Serialize, Deserialize};
use std::path::PathBuf;


#[derive(Serialize, Deserialize, Debug)]
pub struct AliceConfig {
    pub ip_bob: String,
    pub angle_file_path: String,
    pub command_socket_path: String,
}

impl AliceConfig {
    pub fn save_to_file(self, path: &PathBuf){
        let s = serde_json::to_string_pretty(&self).unwrap();
        std::fs::write(path, s).expect("writing config to file");
    }

    pub fn from_pathbuf(path: &PathBuf) -> Self {
        let config_str = std::fs::read_to_string(path)
            .unwrap_or_else(|e| panic!("Failed to read config file {:?}: {}", path, e));
        let config: AliceConfig = serde_json::from_str(&config_str)
            .unwrap_or_else(|e| panic!("Failed to parse config file {:?}: {}", path, e));
        config
    }
}

#[derive(Serialize, Deserialize, Debug)]
pub struct BobConfig {
    pub ip_listen: String,
    pub angle_file_path: String,
    pub click_result_file_path: String,
}

impl BobConfig {
    pub fn save_to_file(self, path: &PathBuf){
        let s = serde_json::to_string_pretty(&self).unwrap();
        std::fs::write(path, s).expect("writing config to file");
    }
    pub fn from_pathbuf(path: &PathBuf) -> Self {
        let config_str = std::fs::read_to_string(path)
            .unwrap_or_else(|e| panic!("Failed to read config file {:?}: {}", path, e));
        let config: BobConfig = serde_json::from_str(&config_str)
            .unwrap_or_else(|e| panic!("Failed to parse config file {:?}: {}", path, e));
        config
    }
}




//#[derive(Debug, Deserialize)]
//pub struct ConfigNetworkAlice {
//    pub ip_bob_qber: String,
//}
//
//
//#[derive(Debug, Deserialize)]
//pub struct ConfigFifoAlice {
//    pub command_socket_path: String,
//    pub angle_file_path: String,
//}
//
//#[derive(Debug, Deserialize)]
//pub struct ConfigFifoBob {
//    pub angle_file_path: String,
//    pub click_result_file_path: String,
//}
//
//
//impl ConfigNetworkAlice{
//    pub fn from_path(path: String) -> Self{
//        let s = std::fs::read_to_string(path).expect("opening config network Alice file");
//        serde_json::from_str(&s).expect("deserializing file")
//    }
//}
//
//impl ConfigFifoAlice{
//    pub fn from_path(path: String) -> Self{
//        let s = std::fs::read_to_string(path).expect("opening config fifo Alice file");
//        serde_json::from_str(&s).expect("deserializing file")
//    }
//}
//
//impl ConfigFifoBob{
//    pub fn from_path(path: String) -> Self{
//        let s = std::fs::read_to_string(path).expect("opening config fifo Bob file");
//        serde_json::from_str(&s).expect("deserializing file")
//    }
//}
