use clap::Parser;
use std::path::PathBuf;

use gen_config::config;

// Built-in local-simulator defaults, so a fresh checkout can run `gen_config`
// with no arguments at all and get a working local sim config set (including
// auto-generated node keys, see config::ensure_sim_node_keys).
const DEFAULT_META_CONFIG: &str = include_str!("../meta_config_for_sim.json");
const DEFAULT_SIM_CONFIG: &str = include_str!("../sim_config.json");

#[derive(Parser, Debug)]
struct Cli {
    /// Path to the meta config file. When omitted, the built-in simulator
    /// meta config is used (and simulator mode is implied).
    #[arg(short = 'c', long)]
    config_path: Option<PathBuf>,
    /// Path to hw_sim.json; Simulator only. When both -c and -s are omitted,
    /// the built-in sim config is used.
    #[arg(short = 's', long)]
    sim: Option<PathBuf>,
    /// Also generate the KMS mTLS certificate chain (needs `openssl`).
    /// Overwrites any previously generated certificates.
    #[arg(short = 'g', long = "gen-certs")]
    gen_certs: bool,
}



fn main() {
    let cli = Cli::parse();

    // create alice and bob direcotry
    std::fs::create_dir_all("alice").expect("creating directory for alice");
    std::fs::create_dir_all("bob").expect("creating directory for bob");

    // read master config; no -c means "local simulator with defaults"
    let config = match &cli.config_path {
        Some(path) => config::Config::from_pathbuf(path),
        None => config::Config::from_json_str(DEFAULT_META_CONFIG),
    };

    // -s selects sim mode; with no arguments at all sim mode is implied,
    // with only -c (real hardware) it is not.
    let sim_json = match (&cli.sim, &cli.config_path) {
        (Some(sim_path), _) => Some(
            std::fs::read_to_string(sim_path).expect("failed reading hw_sim file"),
        ),
        (None, None) => Some(DEFAULT_SIM_CONFIG.to_string()),
        (None, Some(_)) => None,
    };

    // for the simulator
    // - gen sim conf
    // - put alice and bob into the file names
    // - generate missing node keys and derive the peer ids from them
    // for the hardware, use the same config for alice and bob
    let mut for_sim = false;
    let (config_alice, config_bob) = match sim_json {
        Some(sim_json) => {
            for_sim = true;
            let mut config_alice = config.append_extension("_alice");
            let mut config_bob = config.append_extension("_bob");
            config::ensure_sim_node_keys(&mut config_alice, &mut config_bob);
            config::write_sim_config(&config_alice, &config_bob, &sim_json);
            (config_alice, config_bob)
        }
        None => {
            (config.clone(), config.clone())
        }
    };

    config::write_gc_config_alice(&config_alice, for_sim);
    config::write_gc_config_bob(&config_bob, for_sim);

    config::write_qber_config_alice(&config_alice);
    config::write_qber_config_bob(&config_bob);

    config::write_kms_config(&config_alice, &config_bob);
    config::write_node_config(&config_alice, &config_bob);

    config::write_network_alice(&config);
    config::write_network_bob(&config);

    // Certificate generation is opt-in: it shells out to openssl and overwrites
    // any previously generated chain, so it must not run on every config build.
    if cli.gen_certs {
        config::write_certs(&config, &config_alice, &config_bob);
    }
}
