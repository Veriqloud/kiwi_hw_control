use std::net::{TcpListener, TcpStream};
use std::fs::{OpenOptions, File};
use gc::comm::{HwControl, Comm};
use gc::hw::{init_ddr, sync_at_pps, process_stream, gc_for_fpga};
use std::io::{BufWriter, BufReader};
use std::io::prelude::*;
//use std::{thread, time};



struct FileDescriptors {
    // global counter read stream from fpga
    gcr : BufReader<File>,
    // global counter write stream to fpga
    gcw : BufWriter<File>,
    // result fifo to node
    result : BufWriter<File>
}




fn send_gc(alice: &mut TcpStream, files: Option<FileDescriptors>) -> std::io::Result<Option<FileDescriptors>>{
    // reuse file descriptors if already opened earlier
    let mut fd = match files{
        Some(fd) => {fd}
        None => {
            let file_gcr = OpenOptions::new().read(true).open("/dev/xdma0_c2h_0").expect("opening /dev/xdma0_c2h_0");
            let file_gcw =OpenOptions::new().write(true).open("/dev/xdma0_h2c_0").expect("opening /dev/xdma0_h2c_0");
            let file_result = OpenOptions::new().write(true).open("result.f").expect("opening result fifo");

            let fd = FileDescriptors {
                gcr: BufReader::with_capacity(80, file_gcr),
                gcw: BufWriter::with_capacity(80, file_gcw),
                result: BufWriter::with_capacity(80, file_result),
                };
            fd
        }
    };
    // read gc, process, send and write
    let mut alice_buffered = BufWriter::with_capacity(80, alice);
    for i in 0..10000{
        let (_, gc, r) = process_stream(&mut fd.gcr)?;
        if (i%1000)==0 {println!("{:?}\t{:?}\t{:?}", gc, gc as f64 / 80e6, r);};
        alice_buffered.write_all(&gc.to_le_bytes())?;
        //println!("{:?}\t{:?}", raw, gc_for_fpga(gc));
        fd.gcw.write_all(&gc_for_fpga(gc))?;
        //file_gcw.write_all(&raw)?;
        fd.result.write(&[r])?;
    }
    Ok(Some(fd))
}


fn handle_alice(alice: &mut TcpStream) -> std::io::Result<()>{
    let mut files: Option<FileDescriptors> = None;
    loop {
        match alice.recv::<HwControl>() {
            Ok(message) => {
                match message{
                    HwControl::InitDdr => {init_ddr();}
                    HwControl::SyncAtPps => {sync_at_pps();}
                    HwControl::SendGc => {
                        files = send_gc(alice, files)?;
                    }
                    _ => {println!("WARNING: this message should not have been received {:?}", message)}
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

    // delete and remake fifo file for result values
    std::fs::remove_file("result.f").unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
        });
    nix::unistd::mkfifo("result.f", nix::sys::stat::Mode::from_bits(0o644).unwrap())?;
    
    

    let listener = TcpListener::bind("0.0.0.0:15403")
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








