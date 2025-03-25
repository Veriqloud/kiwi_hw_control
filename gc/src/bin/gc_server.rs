use std::net::{TcpListener, TcpStream};
//use std::fs::File;
//use std::io::prelude::*;
use gc::comm::{HwControl, Comm};
use gc::hw::{init_ddr, sync_at_pps};
//use std::{thread, time};



fn send_gc(){
}


fn handle_connection(stream: &mut TcpStream) -> std::io::Result<()>{
    loop {
        match stream.recv::<HwControl>() {
            Ok(message) => {
                println!("message: {:?}", message);
                match message{
                    HwControl::InitDdr => {init_ddr()?;}
                    HwControl::SyncAtPps => {sync_at_pps();}
                    HwControl::SendGc => {send_gc()}
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
