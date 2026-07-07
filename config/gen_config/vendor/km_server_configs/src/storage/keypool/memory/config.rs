use serde::{Deserialize, Serialize};

/// Key lifetime in memory, in milliseconds. Default is 200ms.
#[derive(Debug, Deserialize, Serialize, PartialEq)]
pub struct KeyLifeTimeMs(pub u64);

impl Default for KeyLifeTimeMs {
    fn default() -> Self {
        KeyLifeTimeMs(20000)
    }
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Default)]
pub struct Configuration {
    /// Duration keys will stay in memory, in milliseconds
    #[serde(default)]
    pub key_lifetime_ms: KeyLifeTimeMs,
}
