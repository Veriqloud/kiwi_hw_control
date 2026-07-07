use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub struct Configuration {
    pub keypool: KeyPoolConfigType,
}

impl Default for Configuration {
    fn default() -> Self {
        Self {
            keypool: KeyPoolConfigType::Memory(
                crate::storage::keypool::memory::config::Configuration::default(),
            ),
        }
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub enum KeyPoolConfigType {
    Memory(super::keypool::memory::config::Configuration),
    // FIXME: see https://github.com/Veriqloud/KMS/issues/5
    // Persistent(PersistentTypeConfiguration),
}
