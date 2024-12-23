use std::net::{TcpListener, TcpStream};
use std::fs::File;
//use std::io::prelude::*;
use check_qber::{Message, MessageHeader, rcv, read_angles};
//use std::{thread, time};


fn handle_connection(stream: &mut TcpStream, fifo_a: &mut File, fifo_r: &mut File) 
    -> bool{
    match rcv(stream) {
        Ok(message) => {
            match message.header{
                MessageHeader::Start => {
                    let chunks_to_read = message.body[0] as usize;

                    let angles = read_angles(fifo_a, chunks_to_read)
                        .expect("could not read angles from fifo_a");
                    let results = read_angles(fifo_r, chunks_to_read)
                        .expect("could not read angles from fifo_r");
                    
                    let mr = Message{
                        header: MessageHeader::Angles,
                        body: angles
                    };
                    mr.snd(stream);

                    let mr = Message{
                        header: MessageHeader::Results,
                        body: results
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
    
    let mut fifo_angles = File::open("fifo2")
        .expect("could not open fifo2");
    
    let mut fifo_result = File::open("fifo3")
        .expect("could not open fifo2");

    for stream in listener.incoming(){
        match stream {
            Ok(mut stream) => {
                let mut run = true;
                while run {
                    run = handle_connection(&mut stream, &mut fifo_angles, &mut fifo_result);
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
