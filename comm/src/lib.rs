pub mod gc_comms {
    use serde::{Deserialize, Serialize};

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq)]
    pub enum Request {
        Start,
        Stop,
        DebugOn,
    }

    #[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq)]
    pub enum Response {
        Done,
        DidNothing,
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
