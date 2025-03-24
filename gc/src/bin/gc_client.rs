use clap::{Parser};
use std::fs;
//use std::fs::File;
use serde::Deserialize;
use gc::{Message, MessageHeader, rcv, ControlMessage};
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

fn interaction_with_bob(rx: Receiver<ControlMessage>, ip_bob: String) -> u32{
    println!{"interaction with bob"};

    let mut stream = TcpStream::connect(ip_bob)
        .expect("could not connect to stream\n");

    loop {
        match rx.recv().unwrap() {
            ControlMessage::Start => {
                // send InitDdr to Bob
                let m = Message{
                    header : MessageHeader::InitDdr,
                    body : vec![0],
                };
                m.snd(&mut stream);
                // loop until Stop
                loop {
                    thread::sleep(time::Duration::from_millis(100));
                    match rx.try_recv() {
                        Ok(m) => match m {
                            ControlMessage::Stop => {
                                // send Stop to Bob
                                let m = Message{
                                    header : MessageHeader::Stop,
                                    body : vec![0],
                                };
                                m.snd(&mut stream);
                                break
                            }
                            _ => {}
                            }
                        Err(e) => match e{
                            TryRecvError => {},
                            _ => panic!("rx channel broken")
                        }
                    }
                }
            }
            _ => {}
        }
    }
    return 0;
}

    



fn interaction_with_control(tx: Sender<ControlMessage>) -> u32{
    
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
                let message = ControlMessage::from(message_b[0]);
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
    configfile.push("config.json");

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












