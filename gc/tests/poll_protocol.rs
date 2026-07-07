//! End-to-end test of the node readiness-poll protocol against the real gc
//! binaries. Only the control-socket path is exercised (no Start), so no
//! FPGA/fifo hardware is needed: gc answers PollHwReady from the calibration
//! flag file and raises the node-idle flag for hws when polled while idle.

use std::io::ErrorKind;
use std::os::unix::net::UnixStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::time::{Duration, Instant};

use comm::gc_comms::{Request, Response};
use comm::{read_message, write_message};

struct TestDir {
    path: PathBuf,
}

impl TestDir {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!(
            "gc_poll_test_{name}_{}",
            std::process::id()
        ));
        // stale leftovers from a killed previous run
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("creating test dir");
        Self { path }
    }

    fn file(&self, name: &str) -> String {
        self.path.join(name).to_str().unwrap().to_string()
    }
}

impl Drop for TestDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

struct ChildGuard(Child);

impl Drop for ChildGuard {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn connect_control_socket(path: &str) -> UnixStream {
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        match UnixStream::connect(path) {
            Ok(stream) => {
                stream
                    .set_read_timeout(Some(Duration::from_secs(5)))
                    .unwrap();
                return stream;
            }
            Err(e)
                if matches!(e.kind(), ErrorKind::NotFound | ErrorKind::ConnectionRefused)
                    && Instant::now() < deadline =>
            {
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => panic!("could not connect to control socket {path}: {e}"),
        }
    }
}

fn poll(stream: &mut UnixStream) -> Response {
    write_message(stream, Request::PollHwReady).expect("sending PollHwReady");
    read_message::<Response, _>(stream).expect("reading poll reply")
}

fn wait_for_flag(path: &str, should_exist: bool) {
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if Path::new(path).exists() == should_exist {
            return;
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    panic!(
        "flag {path} did not become {} in time",
        if should_exist { "present" } else { "absent" }
    );
}

/// The poll dance shared by both players: not ready -> HwNotReady + node-idle
/// raised; ready -> HwReady + node-idle lowered; not ready again -> back.
fn run_poll_dance(stream: &mut UnixStream, ready_flag: &str, idle_flag: &str) {
    // no calibration flag: not ready, and gc (idle, nothing streaming)
    // acknowledges the idle node to hws by raising the node-idle flag
    assert_eq!(poll(stream), Response::HwNotReady);
    wait_for_flag(idle_flag, true);

    // calibration done: hws raises the ready flag
    std::fs::File::create(ready_flag).unwrap();
    assert_eq!(poll(stream), Response::HwReady);
    wait_for_flag(idle_flag, false);

    // hws full_init lowers the flag again
    std::fs::remove_file(ready_flag).unwrap();
    assert_eq!(poll(stream), Response::HwNotReady);
    wait_for_flag(idle_flag, true);
}

#[test]
fn gc_alice_answers_readiness_polls_from_flag_files() {
    let dir = TestDir::new("alice");
    let socket = dir.file("startstop.s");
    let ready_flag = dir.file("qkd_ready");
    let idle_flag = dir.file("node_idle");

    let config = serde_json::json!({
        "player": { "Alice": {
            "fifo": {
                "command_socket_path": socket,
                "gc_file_path": dir.file("gc.fifo"),
            },
            "network": { "ip_gc": "127.0.0.1:57381" },
        }},
        "current_hw_parameters_file_path": dir.file("hw_params.txt"),
        "fpga_start_socket_path": dir.file("fpga"),
        "log_level": "Info",
        "ready_flag_path": ready_flag,
        "node_idle_flag_path": idle_flag,
    });
    let config_path = dir.file("gc.json");
    std::fs::write(&config_path, config.to_string()).unwrap();

    let _child = ChildGuard(
        Command::new(env!("CARGO_BIN_EXE_alice"))
            .args(["-c", &config_path, "--logs-location", &dir.file("logs")])
            .spawn()
            .expect("spawning gc-alice"),
    );

    let mut stream = connect_control_socket(&socket);
    run_poll_dance(&mut stream, &ready_flag, &idle_flag);
}

#[test]
fn gc_bob_answers_readiness_polls_from_flag_files() {
    let dir = TestDir::new("bob");
    let socket = dir.file("startstop.s");
    let ready_flag = dir.file("qkd_ready");
    let idle_flag = dir.file("node_idle");

    let config = serde_json::json!({
        "player": { "Bob": {
            "fifo": {
                "command_socket_path": socket,
                "gcr_file_path": dir.file("gcr.fifo"),
                "gc_file_path": dir.file("gc.fifo"),
                "click_result_file_path": dir.file("result.f"),
                "gcuser_file_path": "",
            },
            "network": { "ip_gc": "127.0.0.1:57382" },
        }},
        "current_hw_parameters_file_path": dir.file("hw_params.txt"),
        "fpga_start_socket_path": dir.file("fpga"),
        "log_level": "Info",
        "ready_flag_path": ready_flag,
        "node_idle_flag_path": idle_flag,
    });
    let config_path = dir.file("gc.json");
    std::fs::write(&config_path, config.to_string()).unwrap();

    let _child = ChildGuard(
        Command::new(env!("CARGO_BIN_EXE_bob"))
            .args(["-c", &config_path, "--logs-location", &dir.file("logs")])
            .spawn()
            .expect("spawning gc-bob"),
    );

    let mut stream = connect_control_socket(&socket);
    run_poll_dance(&mut stream, &ready_flag, &idle_flag);

    // Start/Stop are not valid on Bob's socket (sessions come from gc-alice
    // over TCP); they must be answered with DidNothing, not crash gc-bob
    write_message(&mut stream, Request::Start).unwrap();
    assert_eq!(
        read_message::<Response, _>(&mut stream).unwrap(),
        Response::DidNothing
    );
    assert_eq!(poll(&mut stream), Response::HwNotReady);
}
