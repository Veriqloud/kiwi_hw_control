//use std::str::FromStr;
use serde::Deserialize;






#[derive(Debug, Deserialize)]
pub struct ConfigNetworkAlice {
    pub bob_gc: String,
    pub bob_qber: String,
}


#[derive(Debug, Deserialize)]
pub struct ConfigFifoAlice {
    pub command_socket_path: String,
    pub angle_file_path: String,
}

#[derive(Debug, Deserialize)]
pub struct ConfigFifoBob {
    pub command_socket_path: String,
    pub angle_file_path: String,
    pub click_result_file_path: String,
}




//impl Default for ConfigNetworkAlice {
//    fn default() -> Self {
//        Self {
//            bob_gc: String::from_str("192.168.1.77:15403").unwrap(),
//            bob_qber: String::from_str("192.168.1.77:15404").unwrap(),
//        }
//    }
//}
//
//
//impl Default for ConfigFifoAlice {
//    fn default() -> Self {
//        Self {
//            command_socket_path: String::from_str("~/qline/startstop.s").unwrap(),
//            angle_file_path: String::from_str("/dev/xdma0_c2h_3").unwrap(),
//        }
//    }
//}
//
//
//impl Default for ConfigFifoBob {
//    fn default() -> Self {
//        Self {
//            command_socket_path: String::from_str("~/qline/startstop.s").unwrap(),
//            angle_file_path: String::from_str("/dev/xdma0_c2h_3").unwrap(),
//            click_result_file_path: String::from_str("~/qline/result.f").unwrap(),
//        }
//    }
//}
