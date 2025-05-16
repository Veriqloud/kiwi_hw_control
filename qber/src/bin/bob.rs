use clap::Parser;
use qber::config::ConfigFifoBob;
use std::net::{TcpListener, TcpStream};
use std::fs::{OpenOptions, File};
use std::io::prelude::*;
use qber::comm::{Qber, Comm};
//use std::{thread, time};



struct FileDescriptors {
    // angles from fpga fifo
    angles : File,
    // result from Linux fifo
    result : File
}


#[derive(Parser, Debug)]
struct Cli {
    /// Provide a config file for the fifos.
    #[arg(short, default_value="/home/vq-user/qline/config/fifos.json")]
    pub fifo_path: String,
}


fn send_angles(alice: &mut TcpStream, fifos: &ConfigFifoBob, files: Option<FileDescriptors>) -> std::io::Result<Option<FileDescriptors>>{
    // reuse file descriptors if already opened earlier
    let mut fd = match files{
        Some(fd) => {fd}
        None => {
            let fd = FileDescriptors {
                angles: OpenOptions::new().read(true).open(&fifos.angle_file_path).expect("opening angle file"),
                result: OpenOptions::new().read(true).open(&fifos.click_result_file_path).expect("opening result fifo"),
                };
            fd
        }
    };
    // angles stream is 128bit = 64 angles
    let mut buf: [u8;4] = [0;4];
    alice.read_exact(&mut buf)?;
    let num = u32::from_le_bytes(buf);
    for _i in 0..num/32{
        let mut a : [u8;16] = [0; 16];
        let mut r : [u8;32] = [0; 32];
        fd.result.read_exact(&mut r)?;
        fd.angles.read_exact(&mut a)?;
        alice.write_all(&a)?;
        alice.write_all(&r)?;
    }
    Ok(Some(fd))
}


fn handle_alice(alice: &mut TcpStream, fifos: &ConfigFifoBob) -> std::io::Result<()>{
    let mut files: Option<FileDescriptors> = None;
    loop {
        match alice.recv::<Qber>() {
            Ok(message) => {
                match message{
                    Qber::SendAngles => {
                        files = send_angles(alice, &fifos, files)?;
                    }
                }
            }
            Err(err) => {
                println!("no message received");
                return Err(err)
            }
        }
    }
}


fn main() -> std::io::Result<()> {
    
    let cli = Cli::parse();
    let fifos = ConfigFifoBob::from_path(cli.fifo_path);

    let listener = TcpListener::bind("0.0.0.0:15404")
        .expect("TcpListener could not bind to address\n");
    
    loop {
        for stream in listener.incoming(){
            match stream {
                Ok(mut alice) => {
                    println!("connected to Alice");
                    handle_alice(&mut alice, &fifos).unwrap_or_else(|e| match e.kind(){
                        std::io::ErrorKind::BrokenPipe => println!("Warning: Broken Pipe; closing stream"),
                        std::io::ErrorKind::Other => println!("{}", e),
                        std::io::ErrorKind::ConnectionReset => println!("{}", e),
                        _ => panic!("{}", e),
                        });
                }
                Err(err) => {
                    println!("Error: {}", err);
                    break;
                }
            }
        }
    }
}








