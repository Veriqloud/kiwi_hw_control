use clap::Parser;
use comm::qber_comms::Qber;
use comm::read_message;
//use serde::Deserialize;
use std::fs::{File, OpenOptions};
use std::io::prelude::*;
use std::net::{TcpListener, TcpStream};
use qber::config::BobConfig;
use std::path::PathBuf;

struct FileDescriptors {
    // angles from fpga fifo
    angles: File,
    // result from Linux fifo
    result: File,
}

#[derive(Parser, Debug)]
struct Cli {
    /// Path to the configuration file.
    #[arg(short, default_value_os_t = PathBuf::from("/home/vq-user/config/qber.json"))]
    pub config_path: PathBuf,
}


// send all the angles
fn send_angles(
    alice: &mut TcpStream,
    config: &BobConfig,
    files: Option<FileDescriptors>,
) -> std::io::Result<Option<FileDescriptors>> {

    // reuse file descriptors if already opened earlier
    let mut fd = match files {
        Some(fd) => fd,
        None => {
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
    for _i in 0..num / 32 {
        let mut a: [u8; 16] = [0; 16];
        let mut r: [u8; 32] = [0; 32];
        fd.result.read_exact(&mut r)?;
        fd.angles.read_exact(&mut a)?;
        alice.write_all(&a)?;
        alice.write_all(&r)?;
    }
    Ok(Some(fd))
}

fn handle_alice(alice: &mut TcpStream, config: &BobConfig) -> std::io::Result<()> {
    let mut files: Option<FileDescriptors> = None;
    loop {
        match read_message::<Qber, _>(&mut *alice) {
            Ok(message) => match message {
                Qber::SendAngles => {
                    files = send_angles(alice, &config, files)?;
                }
                Qber::Stop => {return Ok(())}
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
    let config = BobConfig::from_pathbuf(&cli.config_path);

    let listener = TcpListener::bind(&config.ip_listen).expect(
        "TcpListener could not bind to address
",
    );

    loop {
        for stream in listener.incoming() {
            match stream {
                Ok(mut alice) => {
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
