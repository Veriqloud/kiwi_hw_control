use clap::{Parser, Subcommand};
use std::fs;
use serde::Deserialize;
use check_qber::{Message, MessageHeader, rcv};


#[derive(Deserialize, Debug)]
struct Configuration{
    ip_address: String
}


#[derive(Parser)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
    count: u32,
}

#[derive(Subcommand)]
enum Commands {
    /// Print the status of the qline
    Status,
    Init
}




fn main() -> std::io::Result<()> {

    let cli = Cli::parse();

    let config_str = fs::read_to_string("config.json").expect("could not read config file\n");
    let config: Configuration = serde_json::from_str(&config_str).expect("JSON not well formatted\n");


    let mut stream = std::net::TcpStream::connect(config.ip_address).expect("could not connect to stream\n");

    println!("count {:?}", cli.count);

    let m = Message{
        header : MessageHeader::Start,
        body : vec![cli.count],
    };
    m.snd(&mut stream);

    


//    let mut streams = Vec::new();
//    for player in &players {
//        streams.push(
//            std::net::TcpStream::connect(&player.ip_address)
//            .expect("could not connect to stream.\n"));
//    }
//
//    match &cli.command {
//        Some(Commands::Status) => {
//            let m = Message{
//                header : MessageHeader::GetStatus,
//                body : Vec::new(),
//            };
//            for (player,stream) in players.iter().zip(&mut streams){
//                m.snd(stream);
//                println!{"requesting status for {:?}", player.player_name};
//                let mr = rcv(stream)?;
//                println!("response: {:?}", mr);
//            }
//
//        },
//        Some(Commands::Init) => {
//            let m = Message{
//                header : MessageHeader::Init,
//                body : Vec::new(),
//            };
//            for (player,stream) in players.iter().zip(&mut streams){
//                m.snd(stream);
//                println!{"requesting init for {:?}", player.player_name};
//                let mr = rcv(stream)?;
//                println!("response: {:?}", mr);
//            }
//
//        }
//        None => {}
//    }
    Ok(())
}
