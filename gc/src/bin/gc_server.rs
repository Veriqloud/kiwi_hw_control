use std::net::{TcpListener, TcpStream};
//use std::fs::File;
//use std::io::prelude::*;
use gc::{Message, MessageHeader, rcv};
//use std::{thread, time};


fn handle_connection(stream: &mut TcpStream) -> bool{
    match rcv(stream) {
        Ok(message) => {
            match message.header{
                //MessageHeader::Start => {
                //    let chunks_to_read = message.body[0] as usize;

                //    let angles = read_angles(fifo_a, chunks_to_read)
                //        .expect("could not read angles from fifo_a");
                //    let results = read_angles(fifo_r, chunks_to_read)
                //        .expect("could not read angles from fifo_r");
                //    
                //    let mr = Message{
                //        header: MessageHeader::Angles,
                //        body: angles
                //    };
                //    mr.snd(stream);

                //    let mr = Message{
                //        header: MessageHeader::Results,
                //        body: results
                //    };
                //    mr.snd(stream);
                //    return true;
                //},
                MessageHeader::InitDdr => {
                    println!("InitDdr");
                    return false;
                }
            _ => {
                println!("unknow request");
                return false;
            },
            }
        }
        Err(_err) => {
            println!("no message received");
            return false;
        }
    }
}


fn main() -> std::io::Result<()> {


    let listener = TcpListener::bind("0.0.0.0:15403")
        .expect("TcpListener could not bind to address\n");
    
    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                let mut run = true;
                while run {
                    run = handle_connection(&mut stream);
                }
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
    Ok(())
}
