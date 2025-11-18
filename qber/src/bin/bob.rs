use clap::Parser;
use comm::qber_comms::Qber;
use comm::read_message;
//use serde::Deserialize;
use std::fs::{File, OpenOptions};
use std::io::prelude::*;
use std::net::{TcpListener, TcpStream};
use qber::config::BobConfig;
use std::path::PathBuf;
use qber::BATCHSIZE;


#[derive(Parser, Debug)]
struct Cli {
    /// Path to the configuration file.
    #[arg(short, default_value_os_t = PathBuf::from("/home/vq-user/config/qber.json"))]
    pub config_path: PathBuf,
}


// send all the angles
fn send_angles(alice: &mut TcpStream, config: &BobConfig) -> std::io::Result<()> {

    let mut fd_angles = OpenOptions::new()
        .read(true)
        .open(&config.angle_file_path)
        .expect("opening angle file");

    let mut fd_result = OpenOptions::new()
        .read(true)
        .open(&config.click_result_file_path)
        .expect("opening result fifo");

    // loop until qber-alice closes the connection
    loop {
        let mut a: [u8; BATCHSIZE/2] = [0; BATCHSIZE/2];
        let mut r: [u8; BATCHSIZE] = [0; BATCHSIZE];
        fd_result.read_exact(&mut r)?;
        fd_angles.read_exact(&mut a)?;

        match alice.write_all(&a){
            Ok(_) => {},
            Err(e) => {
                match e.kind(){
                    std::io::ErrorKind::ConnectionReset => {
                        return Ok(())
                    },
                    _ => return Err(e)
                }
            }
        }

        match alice.write_all(&r){
            Ok(_) => {},
            Err(e) => {
                match e.kind(){
                    std::io::ErrorKind::ConnectionReset => {
                        return Ok(())
                    },
                    _ => return Err(e)
                }
            }
        }

    }
}


fn handle_alice(alice: &mut TcpStream, config: &BobConfig) -> std::io::Result<()> {
    match read_message::<Qber, _>(&mut *alice) {
        Ok(message) => match message {
            Qber::SendAngles => {
                send_angles(alice, &config)?;
            }
        },
        Err(e) => { return Err(e)}
    }
    Ok(())
}


fn main() -> std::io::Result<()> {
    let cli = Cli::parse();
    let config = BobConfig::from_pathbuf(&cli.config_path);

    let listener = TcpListener::bind(&config.ip_listen).expect(
        "TcpListener could not bind to address
",
    );

    for stream in listener.incoming() {
        match stream {
            Ok(mut alice) => {
                if let Err(e) = handle_alice(&mut alice, &config) {
                    match e.kind() {
                        std::io::ErrorKind::BrokenPipe => {
                            println!("Connection to Alice lost (BrokenPipe).")
                        }
                        std::io::ErrorKind::UnexpectedEof => println!(
                            "Angle or Result File closed unexpectedly"
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
    Ok(())
}









