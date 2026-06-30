use std::str::FromStr;

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub struct Configuration {
    pub unix_socket_path: String,
}

impl Default for Configuration {
    fn default() -> Self {
        Self {
            unix_socket_path: String::from_str("./IPC.sock").unwrap(),
        }
    }
}
