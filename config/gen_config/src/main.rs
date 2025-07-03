use clap::{Parser};
use std::path::PathBuf;
use serde::{Deserialize, Serialize};


#[derive(Parser, Debug)]
struct Cli {
    /// Path to the network file
    #[arg(short = 'n', long)]
    network_path: PathBuf,
    /// Path to the output folder
    #[arg(short = 'o', long)]
    output_path: PathBuf,
    /// Desired log level
    #[arg(short = 'l', long, default_value_t = String::from("INFO"))]
    log_level: String,
    /// Generate for simulator
    #[arg(short = 's', long)]
    sim: bool,
}


#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Ip{
    alice: String,
    bob: String
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Port{
    hw: u32,
    hws: u32,
    gc: u32,
    qber: u32,
    node: u32
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Network{
    ip: Ip,
    port: Port
}

impl Network{
    fn from_pathbuf(path: &PathBuf) -> Network {
        let contents = std::fs::read_to_string(path)
            .expect(&format!("failed reading network file: {path:?}"));
        let network: Network =
            serde_json::from_str(&contents).expect(&format!("failed to parse config: {contents}"));
        network
    }
}


fn main() {

    let cli = Cli::parse();


    let network = Network::from_pathbuf(&cli.network_path);


    // write gc_alice.json file
    let hardcoded_conf = if cli.sim {
        gc::config::Configuration {
            player: gc::config::QlinePlayer::Alice(gc::config::AliceConfig {
                network: gc::config::ConfigNetwork {
                    ip_gc: "localhost:50051".to_string(),
                },
                fifo: gc::config::ConfigFifoAlice {
                    command_socket_path: "/tmp/gc_alice_command.socket".to_string(),
                    gc_file_path: "/tmp/gc_alice_gc.fifo".to_string(),
                },
            }),
            current_hw_parameters_file_path: "../config/alice_hw_params.txt".to_string(),
            fpga_start_socket_path: "/tmp/fpga_alice".to_string(),
            log_level: cli.log_level.clone(),
            } 
        } else {
            gc::config::Configuration {
            player: gc::config::QlinePlayer::Alice(gc::config::AliceConfig {
                network: gc::config::ConfigNetwork {
                    ip_gc: network.ip.alice.clone()+":"+&network.port.gc.to_string(),
                },
                fifo: gc::config::ConfigFifoAlice {
                    command_socket_path: "/home/vq-user/qline/start_stop.socket".to_string(),
                    gc_file_path: "/dev/xdma0_h2c_0".to_string(),
                },
            }),
            current_hw_parameters_file_path: "/home/vq-user/qline/hw_control/config/tmp.txt".to_string(),
            fpga_start_socket_path: "/dev/xdma_user".to_string(),
            log_level: cli.log_level.clone(),
        }
    };
    let mut output_file = cli.output_path.clone();
    output_file.push("gc_alice.json");
    let s = serde_json::to_string_pretty(&hardcoded_conf).unwrap();
    std::fs::write(output_file, s).expect("writing output file");


    // write gc_bob.json file
    let hardcoded_conf = if cli.sim {
        gc::config::Configuration {
            player: gc::config::QlinePlayer::Bob(gc::config::BobConfig {
                network: gc::config::ConfigNetwork {
                    ip_gc: "localhost:50051".to_string(),
                },
                fifo: gc::config::ConfigFifoBob {
                    gcr_file_path: "/tmp/gc_bob_gcr.fifo".to_string(),
                    gc_file_path: "/tmp/gc_bob_gc.fifo".to_string(),
                    click_result_file_path: "/tmp/gc_bob_click_result.fifo".to_string(),
                },
            }),
            current_hw_parameters_file_path: "../config/bob_hw_params.txt".to_string(),
            fpga_start_socket_path: "/tmp/fpga_bob".to_string(),
            log_level: cli.log_level.clone(),
        }
    } else {
        gc::config::Configuration {
            player: gc::config::QlinePlayer::Bob(gc::config::BobConfig {
                network: gc::config::ConfigNetwork {
                    ip_gc: network.ip.bob.clone()+":"+&network.port.gc.to_string(),
                },
                fifo: gc::config::ConfigFifoBob {
                    gcr_file_path: "/dev/xdma0_c2h_1".to_string(),
                    gc_file_path: "/dev/xdma0_h2c_0".to_string(),
                    click_result_file_path: "/home/vq-user/click_result.fifo".to_string(),
                },
            }),
            current_hw_parameters_file_path: "/home/vq-user/qline/hw_control/config/tmp.txt".to_string(),
            fpga_start_socket_path: "/dev/xdma0_user".to_string(),
            log_level: cli.log_level.clone(),
        }
    };
    let mut output_file = cli.output_path.clone();
    output_file.push("gc_bob.json");
    let s = serde_json::to_string_pretty(&hardcoded_conf).unwrap();
    std::fs::write(output_file, s).expect("writing output file");


    // write qber_alice.json
    let hardcoded_conf = if cli.sim {
        qber::config::AliceConfig {
            ip_bob: "127.0.0.1:50052".to_string(),
            angle_file_path: "/tmp/gc_alice_angle.fifo".to_string(),
            command_socket_path: "/tmp/gc_alice_command.socket".to_string(),
        }
    } else {
        qber::config::AliceConfig {
            ip_bob: network.ip.bob.clone()+":"+&network.port.qber.to_string(),
            angle_file_path: "/dev/xdma0_c2h_3".to_string(),
            command_socket_path: "/home/vq-user/qline/start_stop.fifo".to_string(),
        }
    };
    let mut output_file = cli.output_path.clone();
    output_file.push("qber_alice.json");
    let s = serde_json::to_string_pretty(&hardcoded_conf).unwrap();
    std::fs::write(output_file, s).expect("writing output file");


    // write qber_bob.json
    let hardcoded_conf = if cli.sim {
        qber::config::BobConfig {
            ip_listen: "127.0.0.1:50052".to_string(),
            angle_file_path: "/tmp/gc_bob_angle.fifo".to_string(),
            click_result_file_path: "/tmp/gc_bob_click_result.fifo".to_string(),
        }
    } else {
        qber::config::BobConfig {
            ip_listen: network.ip.bob.clone()+":"+&network.port.qber.to_string(),
            angle_file_path: "/dev/xdma0_c2h_3".to_string(),
            click_result_file_path: "/home/vq-user/qline/click_result.fifo".to_string(),
        }
    };
    let mut output_file = cli.output_path.clone();
    output_file.push("qber_bob.json");
    let s = serde_json::to_string_pretty(&hardcoded_conf).unwrap();
    std::fs::write(output_file, s).expect("writing output file");









}









