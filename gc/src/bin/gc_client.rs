use clap::{Parser};
use std::fs;
//use std::fs::File;
use serde::Deserialize;
use gc::{Message, MessageHeader, rcv};
//use std::{thread, time};
use std::path::PathBuf;
use std::env::var;
use std::thread;


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


fn main() -> std::io::Result<()> {

    let cli = Cli::parse();
    println!{"cli: {:?}", cli.save};

    let mut configfile = PathBuf::from(
        var("CONFIGPATH").expect("os variable CONFIGPATH"));
    configfile.push("config.json");

    let config_str = fs::read_to_string(configfile)
        .expect("could not read config file\n");
    let config: Configuration = serde_json::from_str(&config_str)
        .expect("JSON not well formatted\n");


    let mut stream_bob = std::net::TcpStream::connect(config.ip_bob)
        .expect("could not connect to stream\n");
    
    let listener = TcpListener::bind("0.0.0.0:15404")
        .expect("TcpListener could not bind to address\n");


    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                match rcv(stream) {
                    Ok(message) => {
                        match message{
                            ControlMessage::Start => {
                                println!("received Start");
                            }
                            ControlMessage::Stop => {
                                println!("received Stop");
                            }
                        }
                    }
                    Err(_err) => {println!("no message received")}
                }
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }

//    // loop calculating qber
//    for _i in 0..cli.repeat {
//        let m = Message{
//            header : MessageHeader::Start,
//            body : vec![cli.chunks],
//        };
//        m.snd(&mut stream);
//
//        let angles = read_angles(&mut fifo, cli.chunks as usize)
//            .expect("could not read angles from fifo");
//
//        let mr1 = rcv(&mut stream).expect("error receiving angles from Bob");
//        let mr2 = rcv(&mut stream).expect("error receiving results from Bob");
//
//        let qber = calc_qber(angles, mr1.body, mr2.body);
//
//        println!("qber {:?}", qber);
//    }

    // tell server we are done
    let m = Message{
        header : MessageHeader::InitDdr,
        body : vec![0],
    };
    m.snd(&mut stream);


    


    Ok(())
}
