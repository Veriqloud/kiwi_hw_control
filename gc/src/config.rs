use serde::{Deserialize};






#[derive(Debug, Deserialize)]
pub struct ConfigNetworkAlice {
    pub ip_bob_gc: String,
    pub ip_bob_qber: String,
}




impl ConfigNetworkAlice{
    pub fn from_path(path: String) -> Self{
        let s = std::fs::read_to_string(path).expect("opening config network Alice file");
        serde_json::from_str(&s).expect("deserializing file")
    }
}



