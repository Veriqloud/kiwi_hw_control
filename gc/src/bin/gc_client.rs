use clap::{Parser};
use std::fs;
use std::fs::{OpenOptions};
use serde::Deserialize;
use gc::comm::{Request, HwControl, Response, Comm};
use gc::hw::{init_ddr, sync_at_pps, wait_for_pps, gc_for_fpga};
use std::{thread, time};
use std::path::PathBuf;
use std::env::var;
use std::net::{TcpListener, TcpStream};
use std::os::unix::net::UnixListener;
use std::io::prelude::*;
use std::sync::mpsc::{Receiver, Sender, channel, TryRecvError};


#[derive(Deserialize, Debug)]
struct Configuration{
    ip_bob: String
}


#[derive(Parser)]
struct Cli {
    /// number of gc to process before stop
    num: u64,
    /// save result to file
    #[arg(short, long)]
    save: bool
}

fn interaction_with_bob(rx: Receiver<Request>, ip_bob: String){
    println!{"interaction with bob"};

    let mut bob = TcpStream::connect(ip_bob)
        .expect("could not connect to stream\n");

    loop {
        match rx.recv().unwrap() {
            Request::Start => {
                bob.send(HwControl::InitDdr).expect("sending to Bob");
                init_ddr();
                wait_for_pps();
                bob.send(HwControl::SyncAtPps).expect("sending to Bob");
                sync_at_pps();
                // loop until Stop
                loop {
                    bob.send(HwControl::SendGc).expect("sending to Bob");
                    //thread::sleep(time::Duration::from_millis(100));
                    let mut file_gcw = OpenOptions::new().read(true).write(true)
                        .open("/dev/xdma0_c2h_0").expect("opening /dev/xdma0_h2c_0");
                    for i in 0..1000{
                        let mut gc_buf: [u8; 8] = [0; 8];
                        bob.read_exact(&mut gc_buf);
                        let gc = u64::from_le_bytes(gc_buf);
                        file_gcw.write_all(&gc_for_fpga(gc)).expect("writing gc to fpga");
                        if i==0{ println!("{:?}", gc);};
                    }
                    match rx.try_recv() {
                        Ok(m) => match m {
                            Request::Stop => {break}
                            _ => {}
                            }
                        Err(e) => match e{
                            TryRecvError::Empty => {},
                            TryRecvError::Disconnected => panic!("rx channel disconnected")
                        }
                    }
                }
            }
            _ => {}
        }
    }
}

    
fn interaction_with_control(tx: Sender<Request>) -> u32{
    
    // remove unix socket if it exists
    std::fs::remove_file("startstop.s").unwrap_or_else(|e| match e.kind() {
        std::io::ErrorKind::NotFound => (),
        _ => panic!("{}", e),
        });

    let listener = UnixListener::bind("startstop.s")
        .expect("UnixListener could not bind to address\n");

    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                let mut message_b: [u8;1] = [0];
                stream.read(&mut message_b).expect("error receiving control message");
                let message = Request::from(message_b[0]);
                tx.send(message);
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
    return 0;
}


fn main() -> std::io::Result<()> {

    let mut configfile = PathBuf::from(
        var("CONFIGPATH").expect("os variable CONFIGPATH"));
    configfile.push("ip.json");

    let config_str = fs::read_to_string(configfile)
        .expect("could not read config file\n");
    let config: Configuration = serde_json::from_str(&config_str)
        .expect("JSON not well formatted\n");

    let (tx, rx) = channel();
    let thread_join_handle = thread::spawn(move || {
        interaction_with_bob(rx, config.ip_bob);
    });
    interaction_with_control(tx);
    
    let res = thread_join_handle.join();

    Ok(())
}












