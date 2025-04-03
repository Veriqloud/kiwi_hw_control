use std::net::{TcpListener, TcpStream};
use std::fs::{OpenOptions, File};
use std::io::prelude::*;
use gc::comm::{HwControl, Comm};
use gc::hw::{init_ddr, sync_at_pps, process_stream, gc_for_fpga};
//use std::{thread, time};


struct FileDescriptors {
    gcr : File,
    gcw : File,
    fifo : File
}




fn send_gc(stream: &mut TcpStream, files: Option<FileDescriptors>) -> std::io::Result<Option<FileDescriptors>>{
    let mut fd = match files{
        Some(fd) => {fd}
        None => {
            let fd = FileDescriptors {
                gcr: OpenOptions::new().read(true)
                    .open("/dev/xdma0_c2h_0").expect("opening /dev/xdma0_c2h_0"),
                gcw: OpenOptions::new().read(true).write(true)
                    .open("/dev/xdma0_h2c_0").expect("opening /dev/xdma0_h2c_0"),
                fifo: OpenOptions::new().write(true)
                    .open("result.f").expect("opening result fifo"),
                };
            fd
        }
    };
    for i in 0..1000{
        let (_, gc, r) = process_stream(&mut fd.gcr)?;
        if i==0 {println!("{:?}\t{:?}\t{:?}", gc, gc as f64 / 80e6, r);};
        stream.write_all(&gc.to_le_bytes())?;
        //println!("{:?}\t{:?}", raw, gc_for_fpga(gc));
        fd.gcw.write_all(&gc_for_fpga(gc))?;
        //file_gcw.write_all(&raw)?;
        fd.fifo.write(&[r])?;
    }
    Ok(Some(fd))
}


fn handle_connection(stream: &mut TcpStream) -> std::io::Result<()>{
    let mut files: Option<FileDescriptors> = None;
    loop {
        match stream.recv::<HwControl>() {
            Ok(message) => {
                //println!("message: {:?}", message);
                match message{
                    HwControl::InitDdr => {init_ddr();}
                    HwControl::SyncAtPps => {sync_at_pps();}
                    HwControl::SendGc => {
                        files = send_gc(stream, files)?;
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

    // delete and remake fifo file for result values
    std::fs::remove_file("result.f").unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
        });
    nix::unistd::mkfifo("result.f", nix::sys::stat::Mode::from_bits(0o644).unwrap())?;
    
    

    let listener = TcpListener::bind("0.0.0.0:15403")
        .expect("TcpListener could not bind to address\n");
    
    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                handle_connection(&mut stream).unwrap_or_else(|e| match e.kind(){
                    std::io::ErrorKind::BrokenPipe => println!("Warning: Broken Pipe"),
                    _ => panic!("{}", e),
                    });
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
    Ok(())
}
