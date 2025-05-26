use gc::comm::{Comm, HwControl};
use gc::hw::{init_ddr, process_gcr_stream, sync_at_pps, write_gc_to_alice, write_gc_to_fpga};
use std::fs::OpenOptions;
use std::io::prelude::*;
use std::net::{TcpListener, TcpStream};

// read the gcr stream, split gcr, write gc to Alice and r to fifo
fn send_gc(alice: &mut TcpStream) -> std::io::Result<()> {
    let mut file_gcr = OpenOptions::new()
        .read(true)
        .open("/dev/xdma0_c2h_0")
        .expect("opening /dev/xdma0_c2h_0");
    let mut file_gcw = OpenOptions::new()
        .write(true)
        .open("/dev/xdma0_h2c_0")
        .expect("opening /dev/xdma0_h2c_0");
    //let mut file_gcr =  OpenOptions::new().read(true).open("/dev/xdma0_c2h_1").expect("opening /dev/xdma0_c2h_1");
    //let mut file_gcw = OpenOptions::new().write(true).open("/dev/xdma0_h2c_0").expect("opening /dev/xdma0_h2c_0");
    let mut file_result = OpenOptions::new()
        .write(true)
        .open("/home/vq-user/qline/result.f")
        .expect("opening result fifo");
    let mut i = 0;
    loop {
        let (gc, result) = process_gcr_stream(&mut file_gcr)?;
        if (i % 100) == 0 {
            println!("{:?}\t{:?}\t{:?}", gc[0], gc[0] as f64 / 80e6, result[0]);
        };
        write_gc_to_alice(gc, alice)?;
        write_gc_to_fpga(gc, &mut file_gcw)?;
        file_result.write(&result)?;
        i = i + 1;
    }
}

fn handle_alice(alice: &mut TcpStream) -> std::io::Result<()> {
    loop {
        match alice.recv::<HwControl>() {
            Ok(message) => {
                match message {
                    HwControl::InitDdr => {
                        init_ddr(false);
                    }
                    HwControl::SyncAtPps => {
                        sync_at_pps();
                        send_gc(alice)?;
                    } //HwControl::SendGc => {
                      //}
                      //_ => {println!("WARNING: this message should not have been received {:?}", message)}
                }
            }
            Err(err) => {
                println!("no message received");
                return Err(err);
            }
        }
    }
}

fn main() -> std::io::Result<()> {
    // delete and remake fifo file for result values
    std::fs::remove_file("/home/vq-user/qline/result.f").unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
    });
    nix::unistd::mkfifo(
        "/home/vq-user/qline/result.f",
        nix::sys::stat::Mode::from_bits(0o644).unwrap(),
    )?;

    let listener =
        TcpListener::bind("0.0.0.0:15403").expect("TcpListener could not bind to address\n");

    loop {
        for stream in listener.incoming() {
            match stream {
                Ok(mut alice) => {
                    println!("connected to Alice");
                    handle_alice(&mut alice).unwrap_or_else(|e| match e.kind() {
                        std::io::ErrorKind::BrokenPipe => println!(
                            "Broken Pipe; we are probably fine because this is how we stop"
                        ),
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
