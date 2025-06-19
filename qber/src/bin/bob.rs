use clap::Parser;
use comm::qber_comms::Qber;
use comm::read_message;
use serde::Deserialize;
use std::fs::{File, OpenOptions};
use std::io::prelude::*;
use std::net::{TcpListener, TcpStream};

struct FileDescriptors {
    // angles from fpga fifo
    angles: File,
    // result from Linux fifo
    result: File,
}

#[derive(Parser, Debug)]
struct Cli {
    /// Provide a config file for the fifos.
    #[arg(short, default_value = "/home/vq-user/qline/config/fifos.json")]
    pub fifo_path: String,
}

#[derive(Deserialize, Debug)]
struct BobConfig {
    ip_listen_qber: String,
    angle_file_path: String,
    click_result_file_path: String,
}

fn send_angles(
    alice: &mut TcpStream,
    config: &BobConfig,
    files: Option<FileDescriptors>,
) -> std::io::Result<Option<FileDescriptors>> {
    // reuse file descriptors if already opened earlier
    let mut fd = match files {
        Some(fd) => fd,
        None => {
            println!("[qber-bob] Opening Angle FIFO for reading: {}", &config.angle_file_path);
            println!("[qber-bob] Opening Click Result FIFO for reading: {}", &config.click_result_file_path);
            let fd = FileDescriptors {
                angles: OpenOptions::new()
                    .read(true)
                    .open(&config.angle_file_path)
                    .expect("opening angle file"),
                result: OpenOptions::new()
                    .read(true)
                    .open(&config.click_result_file_path)
                    .expect("opening result fifo"),
            };
            fd
        }
    };
    // angles stream is 128bit = 64 angles
    let mut buf: [u8; 4] = [0; 4];
    alice.read_exact(&mut buf)?; // This reads a raw u32, not a length-prefixed bincode message
    let num = u32::from_le_bytes(buf);
    println!("[qber-bob] Alice requested {} clicks. Sending in batches of 32.", num);
    for i in 0..num / 32 {
        let mut a: [u8; 16] = [0; 16];
        let mut r: [u8; 32] = [0; 32];
        fd.result.read_exact(&mut r)?;
        fd.angles.read_exact(&mut a)?;
        println!("[qber-bob] Sending batch {}/{}: angles[0..4]={:?}, results[0..4]={:?}", i + 1, num / 32, &a[0..4], &r[0..4]);
        alice.write_all(&a)?;
        alice.write_all(&r)?;
    }
    Ok(Some(fd))
}

fn handle_alice(alice: &mut TcpStream, config: &BobConfig) -> std::io::Result<()> {
    println!("[qber-bob] Handling connection from: {}", alice.peer_addr()?);
    let mut files: Option<FileDescriptors> = None;
    loop {
        match read_message::<Qber, _>(&mut *alice) {
            Ok(message) => match message {
                Qber::SendAngles => {
                    println!("[qber-bob] Received SendAngles request. Preparing to send angles...");
                    files = send_angles(alice, &config, files)?;
                    println!("[qber-bob] Finished sending angles for this request.");
                }
            },
            Err(err) => {
                // Distinguish between EOF and other errors if possible
                if err.kind() == std::io::ErrorKind::UnexpectedEof {
                    println!("Alice closed the connection.");
                    return Ok(()); // Or break the loop
                }
                println!("Error receiving message: {:?}", err);
                return Err(err);
            }
        }
    }
}

fn main() -> std::io::Result<()> {
    let cli = Cli::parse();
    println!("[qber-bob] Loading configuration from: {}", &cli.fifo_path);
    let config_str = std::fs::read_to_string(&cli.fifo_path)
        .unwrap_or_else(|e| panic!("Failed to read config file {}: {}", &cli.fifo_path, e));
    let config: BobConfig = serde_json::from_str(&config_str)
        .unwrap_or_else(|e| panic!("Failed to parse config file {}: {}", &cli.fifo_path, e));

    println!("[qber-bob] Attempting to bind to TCP listener at: {}", &config.ip_listen_qber);
    let listener = TcpListener::bind(&config.ip_listen_qber).expect(
        "TcpListener could not bind to address
",
    );
    println!("[qber-bob] Successfully bound to {}", listener.local_addr().unwrap());

    loop {
        for stream in listener.incoming() {
            match stream {
                Ok(mut alice) => {
                    println!("[qber-bob] Accepted connection from: {}", alice.peer_addr()?);
                    // Changed unwrap_or_else to be more specific about error handling
                    if let Err(e) = handle_alice(&mut alice, &config) {
                        match e.kind() {
                            std::io::ErrorKind::BrokenPipe => {
                                println!("Connection to Alice lost (BrokenPipe).")
                            }
                            std::io::ErrorKind::ConnectionReset => {
                                println!("Connection to Alice reset.")
                            }
                            std::io::ErrorKind::UnexpectedEof => println!(
                                "Alice closed the connection unexpectedly during handling."
                            ),
                            _ => println!("Error handling Alice: {:?}", e),
                        }
                    }
                    println!("Alice disconnected.");
                }
                Err(err) => {
                    println!("Error accepting connection: {}", err);
                }
            }
        }
    }
}
