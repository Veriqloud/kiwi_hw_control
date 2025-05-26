mod gc_comms {
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
