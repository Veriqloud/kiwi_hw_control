use node::{LibP2P, LibP2PBootNode, PathedKeypair};
use serde::{Deserialize, Serialize};
use simulator_configs::ipc::{AliceIpcConfig, BobIpcConfig};
use std::path::PathBuf;
use km_server_configs::{kme, storage::config::KeyPoolConfigType};
use std::net::{IpAddr, Ipv4Addr};
use std::path::Path;
use std::process::Command;
use std::sync::Arc;
use libp2p::{Multiaddr, PeerId};
use std::str::FromStr;

use gc;

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
struct Ip {
    // client side ethernet
    alice: String,
    bob: String,
    // ethernet between Alice and Bob; provided by the white rabbit switch
    alice_wrs: String,
    bob_wrs: String,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
struct Port {
    // on client side ethernet 
    hw: u16,
    hws: u16,
    mon: u16,
    kms_alice: u16,
    kms_bob: u16,
    // on wrs 
    gc: u16,
    qber: u16,
    node_alice: u16,
    node_bob: u16,
    showlogs: u16,
    // remote service supervisor (restartd), on client side ethernet
    restartd: u16,
    // read-only log server (logd), on client side ethernet
    logd: u16,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
struct File {
    // fifo: global counter and result coming from fpga
    gcr: String,
    // fifo: global counter going back to fpga
    gc: String,
    // fifo: angle of the qubit coming from fpga
    angle: String,
    // fifo: result for the user
    result: String,
    // fifo: optional, copy of gc for the user
    gcuser: String,
    // mmap: fpga control registers
    fpgareg: String,
    // unix socket: start/stop command to gc
    startstop: String,
    // hardware paramters
    hw_params: String,
    // kms fifo path
    kms: String
}

// some kms settings; doesn't cover all possible variants
#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
struct Kms {
    alice_peer_id: String,
    bob_peer_id: String,
    key_lifetime_ms: u64,
    default_key_size: u64,
    max_key_count: u64,
    authentication: bool,
    ca_path: String,
    cert_path: String,
    key_path: String,
}

// some node settings; doesn't cover all possible variants
#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
struct Node {
    key_path: String,
    qtol: f64,
    key_size_per_round: usize,
}

// X.509 / mTLS material used by the KMS SAE API. Mirrors the manual
// KMS_install/Gen_X509 flow: one EC root CA signs a server cert per KME plus a
// client cert for the SAE (etsi_client). Optional in the meta_config; sensible
// VeriQloud defaults are used when the block is absent.
#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
#[serde(default)]
struct Tls {
    // certificate subject fields shared by the root CA
    country: String,
    state: String,
    locality: String,
    org: String,
    org_unit: String,
    ca_cn: String,
    // validity of every generated certificate, in days
    validity_days: u32,
    // elliptic curve for all keys, e.g. "secp384r1"
    ec_curve: String,
    // SAN entries appended to the auto IP-derived ones (e.g. "DNS:myhost")
    extra_sans: Vec<String>,
}

impl Default for Tls {
    fn default() -> Self {
        Self {
            country: "FR".to_string(),
            state: "Paris".to_string(),
            locality: "Paris".to_string(),
            org: "VeriQloud".to_string(),
            org_unit: "Veriqloud-KME".to_string(),
            ca_cn: "VQKME".to_string(),
            validity_days: 1095,
            ec_curve: "secp384r1".to_string(),
            extra_sans: Vec::new(),
        }
    }
}

// SAE identifier presented by the ETSI-14 client. Single source of truth shared
// by the KMS SAE list and the generated client certificate's CN.
const SAE_ID: &str = "sae_id";

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct Config {
    ip: Ip,
    port: Port,
    file: File,
    kms: Kms,
    node: Node,
    #[serde(default)]
    tls: Tls,
}

#[derive(Debug, Deserialize, Serialize, PartialEq, Clone)]
pub struct Network {
    myname: String,
    ip: Ip,
    port: Port,
}


impl File {
    pub fn append_extension(&self, extension: &str) -> File {
        File {
            gcr: self.gcr.clone(),
            gc: self.gc.clone()+&extension,
            angle: self.angle.clone()+&extension,
            result: self.result.clone(),
            gcuser: self.gcuser.clone(),
            fpgareg: self.fpgareg.clone()+&extension,
            startstop: self.startstop.clone(),
            hw_params: self.hw_params.clone()+&extension,
            kms: self.kms.clone()+&extension,
        }
    }
}

impl Kms {
    pub fn append_extension(&self, extension: &str) -> Kms {
        let mut kms = self.clone();
        kms.ca_path = kms.ca_path+&extension;
        kms.cert_path = kms.cert_path+&extension;
        kms.key_path = kms.key_path+&extension;
        return kms
    }
}

impl Node {
    pub fn append_extension(&self, extension: &str) -> Node {
        let mut node = self.clone();
        node.key_path = node.key_path+&extension;
        return node
    }
}



impl Config {
    pub fn from_pathbuf(path: &PathBuf) -> Config {
        let contents =
            std::fs::read_to_string(path).expect(&format!("failed reading network file: {path:?}"));
        let config: Config =
            serde_json::from_str(&contents).expect(&format!("failed to parse config: {contents}"));
        config
    }
    pub fn save_to_file(&self, path: &PathBuf) {
        let s = serde_json::to_string_pretty(&self).unwrap();
        std::fs::write(path, s).expect("writing config to file");
    }
    pub fn append_extension(&self, extension: &str) -> Config {
        Config {
            ip: self.ip.clone(), 
            port: self.port.clone(),
            file: self.file.append_extension(extension),
            kms: self.kms.append_extension(extension),
            node: self.node.append_extension(extension),
            tls: self.tls.clone(),
        }
    }
}


// gc
pub fn write_gc_config_alice(config: &Config, for_sim: bool){
    let ignore_gcr_timeout = if for_sim {true} else {false};
    let gc_conf = gc::config::Configuration {
        player: gc::config::QlinePlayer::Alice(gc::config::AliceConfig {
            network: gc::config::ConfigNetwork {
                ip_gc: config.ip.bob_wrs.clone() + ":" + &config.port.gc.to_string(),
            },
            fifo: gc::config::ConfigFifoAlice {
                command_socket_path: config.file.startstop.clone(),
                gc_file_path: config.file.gc.clone(),
            },
        }),
        current_hw_parameters_file_path: config.file.hw_params.clone(),
        fpga_start_socket_path: config.file.fpgareg.clone(),
        log_level: "Info".to_string(),
        ignore_gcr_timeout: ignore_gcr_timeout,
        ready_flag_path: "/tmp/qkd_ready".to_string(),
        node_idle_flag_path: "/tmp/node_idle".to_string(),
    };
    gc_conf.save_to_file(&PathBuf::from("alice/gc.json"));
}

pub fn write_gc_config_bob(config: &Config, for_sim: bool){
    let ignore_gcr_timeout = if for_sim {true} else {false};
    let gc_conf = gc::config::Configuration {
        player: gc::config::QlinePlayer::Bob(gc::config::BobConfig {
            network: gc::config::ConfigNetwork {
                ip_gc: config.ip.bob_wrs.clone() + ":" + &config.port.gc.to_string(),
            },
            fifo: gc::config::ConfigFifoBob {
                command_socket_path: config.file.startstop.clone(),
                gcr_file_path: config.file.gcr.clone(),
                gc_file_path: config.file.gc.clone(),
                click_result_file_path: config.file.result.clone(),
                gcuser_file_path: config.file.gcuser.clone(),
            },
        }),
        current_hw_parameters_file_path: config.file.hw_params.clone(),
        fpga_start_socket_path: config.file.fpgareg.clone(),
        log_level: "Info".to_string(),
        ignore_gcr_timeout: ignore_gcr_timeout,
        ready_flag_path: "/tmp/qkd_ready".to_string(),
        node_idle_flag_path: "/tmp/node_idle".to_string(),
    };
    gc_conf.save_to_file(&PathBuf::from("bob/gc.json"));
}

// qber
pub fn write_qber_config_alice(config: &Config){
    let qber_conf = qber::config::AliceConfig {
        ip_bob: config.ip.bob_wrs.clone() + ":" + &config.port.qber.to_string(),
        angle_file_path: config.file.angle.clone(),
        command_socket_path: config.file.startstop.clone(),
    };
    qber_conf.save_to_file(&PathBuf::from("alice/qber.json"));
}

pub fn write_qber_config_bob(config: &Config){
    let qber_conf = qber::config::BobConfig {
        ip_listen: config.ip.bob_wrs.clone() + ":" + &config.port.qber.to_string(),
        angle_file_path: config.file.angle.clone(),
        click_result_file_path: config.file.result.clone(),
    };
    qber_conf.save_to_file(&PathBuf::from("bob/qber.json"));
}


// sim
pub fn write_sim_config(config_alice: &Config, config_bob: &Config, hw_sim_path: PathBuf){
    let sim_backend_config_alice_str =
        std::fs::read_to_string(&hw_sim_path).expect("failed reading hw_sim file");
    let sim_backend_config_alice =
        serde_json::from_str::<simulator_configs::backend::Configuration>(
            &sim_backend_config_alice_str,
        )
        .unwrap();

    // hw_sim config Alice
    let ipc = simulator_configs::ipc::Configuration::Alice(AliceIpcConfig {
        command_path: config_alice.file.fpgareg.clone(),
        angle_file_path: config_alice.file.angle.clone(),
        gc_read_file_path: config_alice.file.gc.clone(),
        hw_params_file_path: config_alice.file.hw_params.clone(),
    });
    let sim_config_alice = simulator_configs::Configuration {
        backend_config: sim_backend_config_alice,
        ipc_config: ipc,
        log_level: simulator_configs::LogLevel("Info".to_string()),
    };

    let sim_alice_config_json =
        serde_json::to_string_pretty(&sim_config_alice).expect("serializing hw_sim config");
    std::fs::write("alice/sim.json", sim_alice_config_json).expect("writing hw_sim config to file");

    // hw_sim config Bob
    let ipc = simulator_configs::ipc::Configuration::Bob(BobIpcConfig {
        command_path: config_bob.file.fpgareg.clone(),
        angle_file_path: config_bob.file.angle.clone(),
        gcr_file_path: config_bob.file.gcr.clone(),
        gc_read_file_path: config_bob.file.gc.clone(),
        hw_params_file_path: config_bob.file.hw_params.clone(),
    });
    let sim_config_bob: simulator_configs::Configuration = simulator_configs::Configuration {
        ipc_config: ipc,
        ..sim_config_alice
    };

    let sim_bob_config_json =
        serde_json::to_string_pretty(&sim_config_bob).expect("serializing hw_sim config");
    std::fs::write("bob/sim.json", sim_bob_config_json).expect("writing hw_sim config to file");
}


// kms 
pub fn write_kms_config(config_alice: &Config, config_bob: &Config) {

    let kme_config_alice = kme::config::Configuration {
        cfg_type: kme::config::ConfigType::P2P(
                      kme::p2p::config::Configuration {
                          network_type: Default::default(),
                          authentication: Default::default(),
                          name: config_alice.kms.alice_peer_id.clone(),
                      },
        ),
    };

    let kme_config_bob = kme::config::Configuration {
        cfg_type: kme::config::ConfigType::P2P(
                      kme::p2p::config::Configuration {
                          network_type: Default::default(),
                          authentication: Default::default(),
                          name: config_bob.kms.bob_peer_id.clone(),
                      },
        ),
    };

    // just set the key lifetime easy peasy
    let storage_config_alice = km_server_configs::storage::config::Configuration {
        keypool: KeyPoolConfigType::Memory(
                     km_server_configs::storage::keypool::memory::config::Configuration {
                         key_lifetime_ms: km_server_configs::storage::keypool::memory::config::KeyLifeTimeMs(
                                              config_alice.kms.key_lifetime_ms
                                              ),
                     },
                 ),
    };
    let storage_config_bob = km_server_configs::storage::config::Configuration {
        keypool: KeyPoolConfigType::Memory(
                     km_server_configs::storage::keypool::memory::config::Configuration {
                         key_lifetime_ms: km_server_configs::storage::keypool::memory::config::KeyLifeTimeMs(
                                              config_alice.kms.key_lifetime_ms
                                              ),
                     },
                 ),
    };


    let kme_id_alice = "alice_kme";
    let kme_id_bob = "bob_kme";


    let saes_alice = km_server_configs::sae_api::config::SAES {
        saes: vec![km_server_configs::sae_api::config::SAE {
            id: SAE_ID.to_string()
        }],
        mtls: config_alice.kms.authentication,
        ca_certificate_path: config_alice.kms.ca_path.to_string(),
        server_cert_path: config_alice.kms.cert_path.to_string(),
        server_key_path: config_alice.kms.key_path.to_string(),
    };
    let saes_bob = km_server_configs::sae_api::config::SAES {
        saes: vec![km_server_configs::sae_api::config::SAE {
            id: SAE_ID.to_string()
        }],
        mtls: config_bob.kms.authentication,
        ca_certificate_path: config_bob.kms.ca_path.to_string(),
        server_cert_path: config_bob.kms.cert_path.to_string(),
        server_key_path: config_bob.kms.key_path.to_string(),
    };

    let sae_api_config_alice = km_server_configs::sae_api::config::Configuration {
        api_addr: config_alice.ip.alice.parse::<Ipv4Addr>().expect("parsing ip addr"),
        api_port: config_alice.port.kms_alice,
        kme_id: kme_id_alice.into(),
        default_key_size: config_alice.kms.default_key_size,
        max_key_count: config_alice.kms.max_key_count,
        max_key_per_request: 100,
        max_key_size: 4096,
        min_key_size: 128,
        saes: saes_alice,
    };
    
    let sae_api_config_bob = km_server_configs::sae_api::config::Configuration {
        api_addr: config_bob.ip.bob.parse::<Ipv4Addr>().expect("parsing ip addr"),
        api_port: config_bob.port.kms_bob,
        kme_id: kme_id_bob.into(),
        default_key_size: config_bob.kms.default_key_size,
        max_key_count: config_bob.kms.max_key_count,
        max_key_per_request: 100,
        max_key_size: 4096,
        min_key_size: 128,
        saes: saes_bob,
    };

    let ipc_config_alice = km_server_configs::ipc::config::Configuration {
        unix_socket_path: config_alice.file.kms.clone(),
    };
    let ipc_config_bob = km_server_configs::ipc::config::Configuration {
        unix_socket_path: config_bob.file.kms.clone(),
    };

    let octets = config_alice.ip.alice_wrs.parse::<Ipv4Addr>()
        .expect("parsing bind addr").octets();
    let bind_address = Ipv4Addr::new(octets[0], octets[1], octets[2], 0);

    let kms_conf_alice = km_server_configs::configuration::Configuration {
        kme_config: kme_config_alice,
        storage_config: storage_config_alice,
        sae_api_config: sae_api_config_alice,
        ipc_config: ipc_config_alice,
        bind_address: Arc::new(km_server_configs::BindAddress(IpAddr::V4(bind_address))),
        kme_id: Arc::new(km_server_configs::KmeID(kme_id_alice.to_string())),
        log_level: km_server_configs::LogLevel::default(),
    };
    
    let kms_conf_bob = km_server_configs::configuration::Configuration {
        kme_config: kme_config_bob,
        storage_config: storage_config_bob,
        sae_api_config: sae_api_config_bob,
        ipc_config: ipc_config_bob,
        bind_address: Arc::new(km_server_configs::BindAddress(IpAddr::V4(bind_address))),
        kme_id: Arc::new(km_server_configs::KmeID(kme_id_bob.to_string())),
        log_level: km_server_configs::LogLevel::default(),
    };

    let kms_conf_alice_json = serde_json::to_string_pretty(&kms_conf_alice).expect("kms conf alice struct to json");
    std::fs::write("alice/kms.json", kms_conf_alice_json).expect("writing kms alice config to file");
    
    let kms_conf_bob_json = serde_json::to_string_pretty(&kms_conf_bob).expect("kms conf bob struct to json");
    std::fs::write("bob/kms.json", kms_conf_bob_json).expect("writing kms bob config to file");

}


pub fn write_node_config(config_alice: &Config, config_bob: &Config) {

    let external_address_alice = Multiaddr::from_str(
        &format!("/ip4/{}/tcp/{}", config_alice.ip.alice_wrs, config_alice.port.node_alice))
        .expect("constructing node external_address");
    let bootnode_address = Multiaddr::from_str(
        &format!("/ip4/{}/tcp/{}", config_alice.ip.alice_wrs, config_alice.port.node_alice))
        .expect("constructing node bootnode_address");
    
    let external_address_bob = Multiaddr::from_str(
        &format!("/ip4/{}/tcp/{}", config_bob.ip.bob_wrs, config_bob.port.node_bob))
        .expect("constructing node external_address");


    let node_conf_alice = node::Configuration {
        hardware_type: node::HardwareType::Source {
            command_socket_path: config_alice.file.startstop.clone(),
            angles_file_path: config_alice.file.angle.clone(),
        },
        external_address: Some(external_address_alice),
        peers: vec![
            (
                node::PeerIdentity(config_alice.kms.alice_peer_id.clone()),
                node::PeerHardwareType::Source,
            ),
            (
                node::PeerIdentity(config_alice.kms.bob_peer_id.clone()),
                node::PeerHardwareType::Detector,
            ),
        ],
        libp2p: Some(LibP2P {
            boot_node: LibP2PBootNode {
                address: bootnode_address.clone(),
                peer_id: PeerId::from_str(&config_alice.kms.alice_peer_id).expect("peerid from string"),
            },
            pathedkeypair: PathedKeypair {
                keypair: libp2p::identity::Keypair::generate_ed25519(),
                path: config_alice.node.key_path.clone(),
            },
            pnet_key: None,
        }),
        static_angles: [0, 32, 96, 64],
        stats_file_path: None,
        log_file_path_prefix: None,
        key_size_per_round: Some(config_alice.node.key_size_per_round),
        qtol: config_alice.node.qtol,
        rounds_limit_per_session: 10000000,
        requested_final_key_size: Some(config_alice.kms.default_key_size as usize),
        hw_read_buf_size: None,
        key_storage: node::StorageVariant::Fifo {
            path: config_alice.file.kms.clone(),
        },
        log_level: Some("Info".to_string()),
    };
    
    let node_conf_bob = node::Configuration {
        hardware_type: node::HardwareType::Detector {
            angles_file_path: config_bob.file.angle.clone(),
            click_results_file_path: config_bob.file.result.clone(),
            command_socket_path: config_bob.file.startstop.clone(),
        },
        external_address: Some(external_address_bob),
        peers: vec![
            (
                node::PeerIdentity(config_bob.kms.alice_peer_id.clone()),
                node::PeerHardwareType::Source,
            ),
            (
                node::PeerIdentity(config_bob.kms.bob_peer_id.clone()),
                node::PeerHardwareType::Detector,
            ),
        ],
        libp2p: Some(LibP2P {
            boot_node: LibP2PBootNode {
                address: bootnode_address,
                peer_id: PeerId::from_str(&config_bob.kms.alice_peer_id).expect("peerid from string"),
            },
            pathedkeypair: PathedKeypair {
                keypair: libp2p::identity::Keypair::generate_ed25519(),
                path: config_bob.node.key_path.clone(),
            },
            pnet_key: None,
        }),
        static_angles: [0, 32, 96, 64],
        stats_file_path: None,
        log_file_path_prefix: None,
        key_size_per_round: Some(config_bob.node.key_size_per_round),
        qtol: config_bob.node.qtol,
        rounds_limit_per_session: 10000000,
        requested_final_key_size: Some(config_bob.kms.default_key_size as usize),
        hw_read_buf_size: None,
        key_storage: node::StorageVariant::Fifo {
            path: config_bob.file.kms.clone(),
        },
        log_level: Some("Info".to_string()),
    };

    let node_conf_alice_json = serde_json::to_string_pretty(&node_conf_alice).expect("node conf alice struct to json");
    std::fs::write("alice/node.json", node_conf_alice_json).expect("writing node alice config to file");
    
    let node_conf_bob_json = serde_json::to_string_pretty(&node_conf_bob).expect("node conf bob struct to json");
    std::fs::write("bob/node.json", node_conf_bob_json).expect("writing node bob config to file");

}


pub fn write_network_alice(config: &Config) {
    let network = Network{
        myname: "alice".to_string(),
        ip: config.ip.clone(),
        port: config.port.clone(),
    };
    let network_json = serde_json::to_string_pretty(&network).expect("network conf struct to json");
    std::fs::write("alice/network.json", network_json.clone()).expect("writing network alice config to file");
}


pub fn write_network_bob(config: &Config) {
    let network = Network{
        myname: "bob".to_string(),
        ip: config.ip.clone(),
        port: config.port.clone(),
    };
    let network_json = serde_json::to_string_pretty(&network).expect("network conf struct to json");
    std::fs::write("bob/network.json", network_json).expect("writing network bob config to file");
}


// certificates
//
// Adapts the KMS_install/Gen_X509 OpenSSL flow (option A: shell out to
// `openssl`) but fills the certificate SANs from the meta_config IPs, so the
// manual per-run editing of the `.cnf` files is no longer needed. Produces, into
// a working `certs/` directory, an EC root CA that signs:
//   - a server certificate per KME  (clientAuth + serverAuth)
//   - one client certificate for the SAE / etsi_client  (clientAuth)
// The resulting files are then copied to `alice/`, `bob/` and `client/` under the
// exact basenames the generated kms.json expects (respecting the sim
// `_alice`/`_bob` suffixing), so deployment lines up with the KMS config paths.

// Build a subjectAltName value for a KME server certificate reachable at
// `client_ip`. Also covers the localhost port-forwarding tunnels.
fn server_san(client_ip: &str, extra: &[String]) -> String {
    let mut entries = vec![
        format!("IP:{client_ip}"),
        "DNS:localhost".to_string(),
        "IP:127.0.0.1".to_string(),
    ];
    entries.extend(extra.iter().cloned());
    entries.join(", ")
}

// OpenSSL config for the root CA, including one signing-extension section per
// end-entity (referenced with `-extensions` when signing each CSR).
fn rootca_cnf(tls: &Tls, san_alice: &str, san_bob: &str) -> String {
    format!(
        "[req]\n\
         prompt = no\n\
         distinguished_name = dn\n\
         x509_extensions = v3_ext\n\
         \n\
         [dn]\n\
         C = {c}\n\
         ST = {st}\n\
         L = {l}\n\
         O = {o}\n\
         OU = {ou}\n\
         CN = {cn}\n\
         \n\
         [v3_ext]\n\
         basicConstraints = critical, CA:TRUE\n\
         keyUsage = critical, keyCertSign, cRLSign\n\
         \n\
         [ext_kms_alice]\n\
         keyUsage = critical, digitalSignature\n\
         extendedKeyUsage = clientAuth, serverAuth\n\
         subjectAltName = {san_alice}\n\
         \n\
         [ext_kms_bob]\n\
         keyUsage = critical, digitalSignature\n\
         extendedKeyUsage = clientAuth, serverAuth\n\
         subjectAltName = {san_bob}\n\
         \n\
         [ext_sae_client]\n\
         keyUsage = critical, digitalSignature\n\
         extendedKeyUsage = clientAuth\n\
         subjectAltName = DNS:{sae}\n",
        c = tls.country,
        st = tls.state,
        l = tls.locality,
        o = tls.org,
        ou = tls.org_unit,
        cn = tls.ca_cn,
        san_alice = san_alice,
        san_bob = san_bob,
        sae = SAE_ID,
    )
}

// OpenSSL config for a certificate-signing request: subject CN plus the SAN
// carried as a request extension.
fn csr_cnf(tls: &Tls, cn: &str, san: &str) -> String {
    format!(
        "[req]\n\
         prompt = no\n\
         distinguished_name = dn\n\
         req_extensions = ext\n\
         \n\
         [dn]\n\
         C = {c}\n\
         L = {l}\n\
         O = {o}\n\
         CN = {cn}\n\
         \n\
         [ext]\n\
         subjectAltName = {san}\n",
        c = tls.country,
        l = tls.locality,
        o = tls.org,
        cn = cn,
        san = san,
    )
}

// The generated OpenSSL driver script (option A). Kept as a written, re-runnable
// artifact under certs/ so the flow can also be inspected / run by hand.
fn gen_certs_script(tls: &Tls) -> String {
    format!(
        "#!/bin/bash\n\
         # Generated by gen_config. Regenerates the full KMS mTLS chain.\n\
         set -euo pipefail\n\
         cd \"$(dirname \"$0\")\"\n\
         \n\
         CURVE={curve}\n\
         DAYS={days}\n\
         \n\
         # shared EC parameters\n\
         openssl genpkey -genparam -algorithm EC -out ecp.pem \\\n\
         \x20   -pkeyopt ec_paramgen_curve:$CURVE -pkeyopt ec_param_enc:named_curve\n\
         \n\
         # self-signed root CA\n\
         openssl req -x509 -newkey param:ecp.pem -keyout ca.key -out ca.crt \\\n\
         \x20   -days $DAYS -nodes -config fd_rootca.cnf\n\
         \n\
         # $1 name  $2 csr-config  $3 signing-extension-section\n\
         gen_ee() {{\n\
         \x20   openssl ecparam -in ecp.pem -genkey -noout -out ${{1}}_eckey.pem\n\
         \x20   openssl pkcs8 -topk8 -inform PEM -outform PEM -nocrypt \\\n\
         \x20       -in ${{1}}_eckey.pem -out ${{1}}_pkcs8.key\n\
         \x20   openssl req -new -nodes -key ${{1}}_eckey.pem -out ${{1}}.csr -config $2\n\
         \x20   openssl x509 -req -in ${{1}}.csr -CA ca.crt -CAkey ca.key -CAcreateserial \\\n\
         \x20       -out ${{1}}.pem -days $DAYS -extfile fd_rootca.cnf -extensions $3\n\
         \x20   rm -f ${{1}}_eckey.pem ${{1}}.csr\n\
         }}\n\
         \n\
         gen_ee kms_alice  fd_kms_alice.cnf  ext_kms_alice\n\
         gen_ee kms_bob    fd_kms_bob.cnf    ext_kms_bob\n\
         gen_ee sae_client fd_sae_client.cnf ext_sae_client\n",
        curve = tls.ec_curve,
        days = tls.validity_days,
    )
}

// Basename of a (possibly remote, sim-suffixed) config path, e.g.
// "/home/vq-user/authentication/certs/ca.crt_alice" -> "ca.crt_alice".
fn basename(path: &str) -> &str {
    Path::new(path)
        .file_name()
        .and_then(|s| s.to_str())
        .expect("cert path has a file name")
}

fn copy(from: &str, to: String) {
    std::fs::copy(from, &to).expect(&format!("copying {from} -> {to}"));
}

pub fn write_certs(config: &Config, config_alice: &Config, config_bob: &Config) {
    let tls = &config.tls;
    let certs_dir = Path::new("certs");
    std::fs::create_dir_all(certs_dir).expect("creating certs directory");
    std::fs::create_dir_all("client").expect("creating client directory");

    // SANs derived from the client-facing IPs the ETSI client connects to.
    let san_alice = server_san(&config.ip.alice, &tls.extra_sans);
    let san_bob = server_san(&config.ip.bob, &tls.extra_sans);

    // OpenSSL config files and driver script.
    std::fs::write(certs_dir.join("fd_rootca.cnf"), rootca_cnf(tls, &san_alice, &san_bob))
        .expect("writing fd_rootca.cnf");
    std::fs::write(certs_dir.join("fd_kms_alice.cnf"), csr_cnf(tls, "alice_kme", &san_alice))
        .expect("writing fd_kms_alice.cnf");
    std::fs::write(certs_dir.join("fd_kms_bob.cnf"), csr_cnf(tls, "bob_kme", &san_bob))
        .expect("writing fd_kms_bob.cnf");
    std::fs::write(certs_dir.join("fd_sae_client.cnf"), csr_cnf(tls, SAE_ID, &format!("DNS:{SAE_ID}")))
        .expect("writing fd_sae_client.cnf");
    let script_path = certs_dir.join("gen_certs.sh");
    std::fs::write(&script_path, gen_certs_script(tls)).expect("writing gen_certs.sh");

    // Run the OpenSSL flow.
    let status = Command::new("bash")
        .arg(&script_path)
        .status()
        .expect("running gen_certs.sh (is openssl installed?)");
    assert!(status.success(), "gen_certs.sh failed with status {status}");

    // Place outputs under the exact basenames the generated kms.json expects.
    // For real hardware alice and bob share names; for the simulator the
    // meta_config paths carry the _alice/_bob suffix, which basename() preserves.
    copy("certs/ca.crt", format!("alice/{}", basename(&config_alice.kms.ca_path)));
    copy("certs/kms_alice.pem", format!("alice/{}", basename(&config_alice.kms.cert_path)));
    copy("certs/kms_alice_pkcs8.key", format!("alice/{}", basename(&config_alice.kms.key_path)));

    copy("certs/ca.crt", format!("bob/{}", basename(&config_bob.kms.ca_path)));
    copy("certs/kms_bob.pem", format!("bob/{}", basename(&config_bob.kms.cert_path)));
    copy("certs/kms_bob_pkcs8.key", format!("bob/{}", basename(&config_bob.kms.key_path)));

    // SAE / etsi_client identity stays local (the client runs off-node). These
    // three feed MtlsConfiguration::new(id_cert, id_key, [ca]) in etsi_client.
    copy("certs/sae_client.pem", "client/sae_cert.pem".to_string());
    copy("certs/sae_client_pkcs8.key", "client/sae_key.pem".to_string());
    copy("certs/ca.crt", "client/ca.crt".to_string());

    println!("certificates written to certs/ and copied into alice/, bob/, client/");
}










