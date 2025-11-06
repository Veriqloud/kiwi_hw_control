use simulator_configs::Configuration;
use std::path::PathBuf;

fn write_config(
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






