use std::net::{TcpListener, TcpStream};
use std::fs::OpenOptions;
use std::io::prelude::*;
use gc::comm::{HwControl, Comm};
use gc::hw::{init_ddr, sync_at_pps, process_stream, gc_for_fpga};
//use std::{thread, time};



fn send_gc(stream: &mut TcpStream) -> std::io::Result<()>{
    let mut file_gcr = OpenOptions::new().read(true)
        .open("/dev/xdma0_c2h_0").expect("opening /dev/xdma0_c2h_0");
    let mut file_gcw = OpenOptions::new().read(true).write(true)
        .open("/dev/xdma0_c2h_0").expect("opening /dev/xdma0_h2c_0");
    for i in 0..1000{
        let (_, gc, r) = process_stream(&mut file_gcr)?;
        if i==0 {println!("{:?}\t{:?}", gc, r);};
        stream.write_all(&gc.to_le_bytes())?;
        file_gcw.write_all(&gc_for_fpga(gc))?;
    }
    Ok(())
}


fn handle_connection(stream: &mut TcpStream) -> std::io::Result<()>{
    loop {
        match stream.recv::<HwControl>() {
            Ok(message) => {
                println!("message: {:?}", message);
                match message{
                    HwControl::InitDdr => {init_ddr();}
                    HwControl::SyncAtPps => {sync_at_pps();}
                    HwControl::SendGc => {send_gc(stream)?}
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

    

    let listener = TcpListener::bind("0.0.0.0:15403")
        .expect("TcpListener could not bind to address\n");
    
    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                handle_connection(&mut stream)?;
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
    Ok(())
}
