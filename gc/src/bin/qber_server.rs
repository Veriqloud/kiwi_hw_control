use std::net::{TcpListener, TcpStream};
use std::fs::{OpenOptions, File};
use std::io::prelude::*;
use gc::comm::{HwControl, Comm};
//use std::{thread, time};



struct FileDescriptors {
    // angles from fpga fifo
    angles : File,
    // result from Linux fifo
    result : File
}




fn send_angles(alice: &mut TcpStream, files: Option<FileDescriptors>) -> std::io::Result<Option<FileDescriptors>>{
    // reuse file descriptors if already opened earlier
    let mut fd = match files{
        Some(fd) => {fd}
        None => {
            let fd = FileDescriptors {
                angles: OpenOptions::new().read(true).open("/dev/xdma0_c2h_3").expect("opening /dev/xdma0_c2h_3"),
                result: OpenOptions::new().read(true).open("result.f").expect("opening result fifo"),
                };
            fd
        }
    };
    // angles stream is 128bit = 64 angles
    for _i in 0..1000{
        let mut a : [u8;16] = [0; 16];
        let mut r : [u8;64] = [0; 64];
        fd.result.read_exact(&mut r)?;
        fd.angles.read_exact(&mut a)?;
        alice.write_all(&a)?;
        alice.write_all(&r)?;
    }
    Ok(Some(fd))
}


fn handle_alice(alice: &mut TcpStream) -> std::io::Result<()>{
    let mut files: Option<FileDescriptors> = None;
    loop {
        match alice.recv::<HwControl>() {
            Ok(message) => {
                match message{
                    HwControl::SendAngles => {
                        files = send_angles(alice, files)?;
                    }
                    m => {println!("WARNING: message [{:?}] not treated", m);}
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

    let listener = TcpListener::bind("0.0.0.0:15404")
        .expect("TcpListener could not bind to address\n");
    
    loop {
        for stream in listener.incoming(){
            match stream {
                Ok(mut alice) => {
                    println!("connected to Alice");
                    handle_alice(&mut alice).unwrap_or_else(|e| match e.kind(){
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








