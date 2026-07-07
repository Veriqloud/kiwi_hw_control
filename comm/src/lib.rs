pub mod gc_comms {
    use serde::{Deserialize, Serialize};
    use strum::EnumString;

    /// From node to gc_client
    ///
    /// New variants must be appended at the end: bincode encodes the variant
    /// index, so reordering breaks wire compatibility between node and gc.
    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, EnumString)]
    pub enum Request {
        #[strum(serialize = "1")]
        Start,
        #[strum(serialize = "2")]
        Stop,
        /// Ask gc whether the hardware is calibrated and ready for QKD.
        /// Replied with HwReady or HwNotReady. The node polls this every 2s
        /// while idle (with its DMA fds closed) and at round boundaries.
        #[strum(serialize = "3")]
        PollHwReady,
    }

    /// From gc_client to node
    ///
    /// New variants must be appended at the end: bincode encodes the variant
    /// index, so reordering breaks wire compatibility between node and gc.
    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, EnumString)]
    pub enum Response {
        #[strum(serialize = "1")]
        Done,
        #[strum(serialize = "2")]
        DidNothing,
        /// Reply to PollHwReady: calibration is done, node may start a session.
        #[strum(serialize = "3")]
        HwReady,
        /// Reply to PollHwReady: hardware is not ready (uncalibrated or
        /// calibration in progress); node must close its fifos and keep polling.
        #[strum(serialize = "4")]
        HwNotReady,
    }
}

pub mod qber_comms {
    use serde::{Deserialize, Serialize};

    // Messages from Alice to Bob
    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq)]
    pub enum Qber {
        SendAngles = 4,
    }
}

use serde::{de::DeserializeOwned, Serialize};
use std::fmt::Debug;
use std::io::{Read, Write};

pub fn write_message<T: Serialize + Debug, W: Write>(stream: &mut W, message: T) -> std::io::Result<()> {
    //println!("[qber-comm] WRITE: {:?}", message);
    let serialized_message = bincode::serde::encode_to_vec(&message, bincode::config::standard())
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    let len = serialized_message.len() as u32;

    stream.write_all(&len.to_le_bytes())?;
    stream.write_all(&serialized_message)?;

    Ok(())
}

pub fn read_message<T: DeserializeOwned + Debug, R: Read>(stream: &mut R) -> std::io::Result<T> {
    let mut len_bytes = [0u8; 4]; // u32 is 4 bytes
    stream.read_exact(&mut len_bytes)?;

    let len = u32::from_le_bytes(len_bytes) as usize;

    let mut buffer = vec![0u8; len];
    stream.read_exact(&mut buffer)?;

    let (message, _): (T, usize) =
        bincode::serde::decode_from_slice(&buffer, bincode::config::standard())
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;

    //println!("[qber-comm] READ: {:?}", message);
    Ok(message)
}
