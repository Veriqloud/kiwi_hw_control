use clap::Parser;
use serde::{Deserialize, Serialize};
use simulator_configs::Configuration;
use std::default::Default;
use std::path::PathBuf;

#[derive(Parser, Debug)]
struct Cli {
    /// Path to the network file
    #[arg(short = 'n', long)]
    network_path: PathBuf,
    /// Path to the output folder for Alice; will be created if it does not exist
    #[arg(short = 'a', long)]
    output_path_alice: PathBuf,
    /// Path to the output folder for Bob
    #[arg(short = 'b', long)]
    output_path_bob: PathBuf,
    /// Desired log level
    #[arg(short = 'l', long, default_value_t = String::from("INFO"))]
    log_level: String,
    /// Path to hw_sim.json; Simulator only
    #[arg(short = 's', long)]
    sim: Option<PathBuf>,
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Ip {
    alice: String,
    bob: String,
    alice_wrs: String,
    bob_wrs: String,
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Port {
    hw: u32,
    hws: u32,
    gc: u32,
    qber: u32,
    node: u32,
    mon: u32,
}

#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct Network {
    ip: Ip,
    port: Port,
}

impl Network {
    fn from_pathbuf(path: &PathBuf) -> Network {
        let contents =
            std::fs::read_to_string(path).expect(&format!("failed reading network file: {path:?}"));
        let network: Network =
            serde_json::from_str(&contents).expect(&format!("failed to parse config: {contents}"));
        network
    }
    pub fn save_to_file(&self, path: &PathBuf) {
        let s = serde_json::to_string_pretty(&self).unwrap();
        std::fs::write(path, s).expect("writing config to file");
    }
}

fn main() {
    let cli = Cli::parse();

    if cli.output_path_bob == cli.output_path_alice {
        println!("ERROR: output paths for alice and bob cannot be the same!");
        return;
    }
    std::fs::create_dir_all(&cli.output_path_alice).expect("creating directory for alice");
    std::fs::create_dir_all(&cli.output_path_bob).expect("creating directory for alice");

    let network = Network::from_pathbuf(&cli.network_path);

    match cli.sim {
        Some(hw_sim_path) => {
            // generate files for the simulator

            // gc config Alice
            let hardcoded_conf = gc::config::Configuration {
                player: gc::config::QlinePlayer::Alice(gc::config::AliceConfig {
                    network: gc::config::ConfigNetwork {
                        ip_gc: network.ip.bob.clone() + ":" + &network.port.gc.to_string(),
                    },
                    fifo: gc::config::ConfigFifoAlice {
                        command_socket_path: "/tmp/gc_alice_command.socket".to_string(),
                        gc_file_path: "/tmp/gc_alice_gc.fifo".to_string(),
                    },
                }),
                current_hw_parameters_file_path: std::fs::canonicalize(&cli.output_path_alice)
                    .unwrap()
                    .join("hw_params.txt")
                    .to_str()
                    .unwrap()
                    .to_string(),
                fpga_start_socket_path: "/tmp/fpga_alice".to_string(),
                log_level: cli.log_level.clone(),
            };
            let mut output_file = cli.output_path_alice.clone();
            output_file.push("gc.json");
            println!("writing gc config for Alice to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // gc config Bob
            let hardcoded_conf = gc::config::Configuration {
                player: gc::config::QlinePlayer::Bob(gc::config::BobConfig {
                    network: gc::config::ConfigNetwork {
                        ip_gc: network.ip.bob.clone() + ":" + &network.port.gc.to_string(),
                    },
                    fifo: gc::config::ConfigFifoBob {
                        gcr_file_path: "/tmp/gc_bob_gcr.fifo".to_string(),
                        gc_file_path: "/tmp/gc_bob_gc.fifo".to_string(),
                        click_result_file_path: "/tmp/gc_bob_click_result.fifo".to_string(),
                        gcuser_file_path: "/tmp/gcuser.fifo".to_string(),
                    },
                }),
                current_hw_parameters_file_path: std::fs::canonicalize(&cli.output_path_bob)
                    .unwrap()
                    .join("hw_params.txt")
                    .to_str()
                    .unwrap()
                    .to_string(),
                fpga_start_socket_path: "/tmp/fpga_bob".to_string(),
                log_level: cli.log_level.clone(),
            };
            let mut output_file = cli.output_path_bob.clone();
            output_file.push("gc.json");
            println!("writing gc config for Bob to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // qber config Alice
            let hardcoded_conf = qber::config::AliceConfig {
                ip_bob: network.ip.bob.clone() + ":" + &network.port.qber.to_string(),
                angle_file_path: "/tmp/gc_alice_angle.fifo".to_string(),
                command_socket_path: "/tmp/gc_alice_command.socket".to_string(),
            };
            let mut output_file = cli.output_path_alice.clone();
            output_file.push("qber.json");
            println!("writing gc config for Bob to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // qber config Bob
            let hardcoded_conf = qber::config::BobConfig {
                ip_listen: network.ip.bob.clone() + ":" + &network.port.qber.to_string(),
                angle_file_path: "/tmp/gc_bob_angle.fifo".to_string(),
                click_result_file_path: "/tmp/gc_bob_click_result.fifo".to_string(),
            };
            let mut output_file = cli.output_path_bob.clone();
            output_file.push("qber.json");
            println!("writing gc config for Bob to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // writing dummy hw_params file
            let s = "fiber_delay\t100\ndecoy_delay\t100";
            // Alice
            let mut output_file = cli.output_path_alice.clone();
            output_file.push("hw_params.txt");
            println!("writing dummy hw params to {:?}", &output_file);
            std::fs::write(output_file, s).expect("writing hw_params to file");
            // Bob
            let mut output_file = cli.output_path_bob.clone();
            output_file.push("hw_params.txt");
            println!("writing dummy hw params to {:?}", &output_file);
            std::fs::write(output_file, s).expect("writing hw_params to file");

            write_hw_sim_configurations(
                hw_sim_path,
                cli.output_path_alice,
                cli.output_path_bob,
                cli.log_level,
            );
        }
        None => {
            // generate files for the real hardware

            // gc config Alice
            let hardcoded_conf = gc::config::Configuration {
                player: gc::config::QlinePlayer::Alice(gc::config::AliceConfig {
                    network: gc::config::ConfigNetwork {
                        ip_gc: network.ip.bob_wrs.clone() + ":" + &network.port.gc.to_string(),
                    },
                    fifo: gc::config::ConfigFifoAlice {
                        command_socket_path: "/home/vq-user/start_stop.socket".to_string(),
                        gc_file_path: "/dev/xdma0_h2c_0".to_string(),
                    },
                }),
                current_hw_parameters_file_path: "/home/vq-user/hw_control/config/tmp.txt"
                    .to_string(),
                fpga_start_socket_path: "/dev/xdma0_user".to_string(),
                log_level: cli.log_level.clone(),
            };
            let mut output_file = cli.output_path_alice.clone();
            output_file.push("gc.json");
            println!("writing gc config for Alice to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // gc config Bob
            let hardcoded_conf = gc::config::Configuration {
                player: gc::config::QlinePlayer::Bob(gc::config::BobConfig {
                    network: gc::config::ConfigNetwork {
                        ip_gc: network.ip.bob_wrs.clone() + ":" + &network.port.gc.to_string(),
                    },
                    fifo: gc::config::ConfigFifoBob {
                        gcr_file_path: "/dev/xdma0_c2h_1".to_string(),
                        gc_file_path: "/dev/xdma0_h2c_0".to_string(),
                        click_result_file_path: "/home/vq-user/click_result.fifo".to_string(),
                        gcuser_file_path: "/tmp/gcuser.fifo".to_string(),
                    },
                }),
                current_hw_parameters_file_path: "/home/vq-user/hw_control/config/tmp.txt"
                    .to_string(),
                fpga_start_socket_path: "/dev/xdma0_user".to_string(),
                log_level: cli.log_level.clone(),
            };
            let mut output_file = cli.output_path_bob.clone();
            output_file.push("gc.json");
            println!("writing gc config for Bob to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // qber config Alice
            let hardcoded_conf = qber::config::AliceConfig {
                ip_bob: network.ip.bob_wrs.clone() + ":" + &network.port.qber.to_string(),
                angle_file_path: "/dev/xdma0_c2h_3".to_string(),
                command_socket_path: "/home/vq-user/start_stop.socket".to_string(),
            };
            let mut output_file = cli.output_path_alice.clone();
            output_file.push("qber.json");
            println!("writing qber config for Alice to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // qber config Bob
            let hardcoded_conf = qber::config::BobConfig {
                ip_listen: network.ip.bob_wrs.clone() + ":" + &network.port.qber.to_string(),
                angle_file_path: "/dev/xdma0_c2h_3".to_string(),
                click_result_file_path: "/home/vq-user/click_result.fifo".to_string(),
            };
            let mut output_file = cli.output_path_bob.clone();
            output_file.push("qber.json");
            println!("writing qber config for Bob to {:?}", output_file);
            hardcoded_conf.save_to_file(&output_file);

            // cp network.json for Alice
            let mut output_file = cli.output_path_alice.clone();
            output_file.push("network.json");
            println!("copying network.json to {:?}", output_file);
            network.save_to_file(&output_file);

            // cp network.json for Bob
            let mut output_file = cli.output_path_bob.clone();
            output_file.push("network.json");
            println!("copying network.json to {:?}", output_file);
            network.save_to_file(&output_file);
        }
    }
}

fn write_hw_sim_configurations(
    hw_sim_path: PathBuf,
    alice_output_path: PathBuf,
    bob_output_path: PathBuf,
    log_level: String,
) {
    // hw_sim config Alice
    let sim_backend_config_alice_str =
        std::fs::read_to_string(&hw_sim_path).expect("failed reading hw_sim file");
    let sim_backend_config_alice =
        serde_json::from_str::<simulator_configs::backend::Configuration>(
            &sim_backend_config_alice_str,
        )
        .unwrap();

    let sim_config_alice = Configuration {
        backend_config: sim_backend_config_alice,
        ipc_config: simulator_configs::ipc::Configuration::Alice(Default::default()),
        log_level: simulator_configs::LogLevel(log_level.clone()),
    };

    let output_file = alice_output_path.join("hw_sim.json");
    println!("writing hw_sim config for Alice to {:?}", output_file);
    let sim_alice_config_json =
        serde_json::to_string_pretty(&sim_config_alice).expect("serializing hw_sim config");
    std::fs::write(&output_file, sim_alice_config_json).expect("writing hw_sim config to file");

    // hw_sim config Bob
    let sim_config_bob: simulator_configs::Configuration = Configuration {
        ipc_config: simulator_configs::ipc::Configuration::default(),
        ..sim_config_alice
    };

    let output_file = bob_output_path.join("hw_sim.json");
    println!("writing hw_sim config for Bob to {:?}", output_file);
    let sim_bob_config_json =
        serde_json::to_string_pretty(&sim_config_bob).expect("serializing hw_sim config");
    std::fs::write(&output_file, sim_bob_config_json).expect("writing hw_sim config to file");
}
