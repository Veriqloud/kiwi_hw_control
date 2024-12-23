use std::net::{TcpListener, TcpStream};
use std::fs::File;
//use std::io::prelude::*;
use check_qber::{Message, MessageHeader, rcv, read_angles};
//use std::{thread, time};


fn handle_connection(stream: &mut TcpStream, fifo: &mut File) -> bool{
    match rcv(stream) {
        Ok(message) => {
            match message.header{
                MessageHeader::Start => {
                    let chunks_to_read = message.body[0] as usize;

                    let angles = read_angles(fifo, chunks_to_read)
                        .expect("could not read angles from fifo");
                    
                    let mr = Message{
                        header: MessageHeader::Angles,
                        body: angles
                    };
                    mr.snd(stream);
                    return true;
                },
                MessageHeader::Done => {
                    println!("got message done");
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
    
    let mut fifo = File::open("fifo2")
        .expect("could not open fifo2");

    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                let mut run = true;
                while run {
                    run = handle_connection(&mut stream, &mut fifo);
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
