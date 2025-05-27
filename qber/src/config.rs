use serde::{Deserialize};






#[derive(Debug, Deserialize)]
pub struct ConfigNetworkAlice {
    pub ip_bob_gc: String,
    pub ip_bob_qber: String,
}


#[derive(Debug, Deserialize)]
pub struct ConfigFifoAlice {
    pub command_socket_path: String,
    pub gc_file_path: String,
    pub angle_file_path: String,
}

#[derive(Debug, Deserialize)]
pub struct ConfigFifoBob {
    pub angle_file_path: String,
    pub gcr_file_path: String,
    pub gc_file_path: String,
    pub click_result_file_path: String,
}


impl ConfigNetworkAlice{
    pub fn from_path(path: String) -> Self{
        let s = std::fs::read_to_string(path).expect("opening config network Alice file");
        serde_json::from_str(&s).expect("deserializing file")
    }
}

impl ConfigFifoAlice{
    pub fn from_path(path: String) -> Self{
        let s = std::fs::read_to_string(path).expect("opening config fifo Alice file");
        serde_json::from_str(&s).expect("deserializing file")
    }
}

impl ConfigFifoBob{
    pub fn from_path(path: String) -> Self{
        let s = std::fs::read_to_string(path).expect("opening config fifo Bob file");
        serde_json::from_str(&s).expect("deserializing file")
    }
}


