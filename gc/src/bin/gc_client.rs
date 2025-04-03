use clap::{Parser};
use std::fs;
use std::fs::{OpenOptions};
use gc::comm::{Request, Response, HwControl, Comm};
use gc::hw::{init_ddr, sync_at_pps, wait_for_pps, gc_for_fpga};
use std::thread;
use std::path::PathBuf;
use std::env::var;
use std::net::TcpStream;
use std::os::unix::net::UnixListener;
use std::io::prelude::*;
use std::sync::mpsc::{Receiver, Sender, channel, TryRecvError};
use serde::Deserialize;


#[derive(Deserialize, Clone, Debug)]
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

fn interaction_with_bob(rx: Receiver<Request>, tx: Sender<Response>, ip_bob: String) -> std::io::Result<()>{
    println!{"interaction with bob"};

    let mut bob = TcpStream::connect(ip_bob)
        .expect("could not connect to stream\n");

    loop {
        match rx.recv().unwrap() {
            Request::Start => {
                bob.send(HwControl::InitDdr).expect("sending to Bob");
                init_ddr();
                tx.send(Response::Done).expect("sending message through c2");
                wait_for_pps();
                bob.send(HwControl::SyncAtPps).expect("sending to Bob");
                sync_at_pps();
                let mut file_gcw = OpenOptions::new().read(true).write(true)
                    .open("/dev/xdma0_h2c_0").expect("opening /dev/xdma0_h2c_0");
                println!("files opened");
                // loop until Stop
                let mut j = 0;
                loop {
                    bob.send(HwControl::SendGc).expect("sending to Bob");
                    //thread::sleep(time::Duration::from_millis(100));
                    for i in 0..1000{
                        let mut gc_buf: [u8; 8] = [0; 8];
                        bob.read_exact(&mut gc_buf)?;
                        let gc = u64::from_le_bytes(gc_buf);
                        file_gcw.write_all(&gc_for_fpga(gc)).expect("writing gc to fpga");
                        if i==0{ println!("{:?}\t{:?}", j, gc);};
                    }
                    j += 1;
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
            _ => {
                tx.send(Response::DidNothing).expect("sending message through c2");
            }
        }
    }
}

    
fn interaction_with_control(tx: Sender<Request>, rx: Receiver<Response>) {
    
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
                let message: Request = stream.recv().expect("recv");
                tx.send(message).expect("sending message through  channel");
                let m =  rx.recv().unwrap();
                stream.send(m).expect("sending message");
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
}


fn main() -> std::io::Result<()> {


    loop {
        let mut configfile = PathBuf::from(
            var("CONFIGPATH").expect("os variable CONFIGPATH"));
        configfile.push("ip.json");

        let config_str = fs::read_to_string(configfile)
            .expect("could not read config file\n");
        let config: Configuration = serde_json::from_str(&config_str)
            .expect("JSON not well formatted\n");

        let (c1_tx, c1_rx) = channel();
        let (c2_tx, c2_rx) = channel();
        let thread_join_handle = thread::spawn(move || {
            interaction_with_bob(c1_rx, c2_tx, config.ip_bob)
                .unwrap_or_else(|e| match e.kind(){
                    std::io::ErrorKind::UnexpectedEof => println!("Warning: Unexpected Eof"),
                    _                                 => panic!("interaction with bob {}", e),
            });
        });
        interaction_with_control(c1_tx, c2_rx);
        
        thread_join_handle.join().expect("joining thread");
    }

}












