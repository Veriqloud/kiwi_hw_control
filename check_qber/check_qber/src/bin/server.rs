use std::net::{TcpListener, TcpStream};
use std::fs::File;
use std::io::prelude::*;
use check_qber::{Message, MessageHeader, rcv};


fn handle_connection(mut stream: TcpStream){
    match rcv(&mut stream) {
        Ok(message) => {
            match message.header{
                MessageHeader::Start => {
                    let angles_to_read = message.body[0] as usize;
                    println!("reading angles ...");
                    let mut fifo = File::open("fifo2")
                        .expect("could not open fifo2");
                    let mut buf = [0;16];
                    let mut angles = Vec::<u8>::with_capacity(angles_to_read/4);
                    while angles.len()<angles_to_read/4 {
                        fifo.read_exact(&mut buf)
                            .expect("error reading fifo");
                        angles.extend(&buf);
                    }
                    println!("finished reading angles");
                    let mr = Message{
                        header: MessageHeader::Done,
                        body: vec![0,0]
                    };
                    mr.snd(&mut stream);
                },
                MessageHeader::Angles => {
                    println!("processing ...");
                    let angles = message.body;
                    let mr = Message{
                        header: MessageHeader::Done,
                        body: vec![0,0]
                    };
                    mr.snd(&mut stream);
                },
            _ => {println!("unknow request")},
            }
        }
        Err(_err) => {
            println!("no message received");
        }
    }
}


fn main() -> std::io::Result<()> {

    let listener = TcpListener::bind("0.0.0.0:15403")
        .expect("TcpListener could not bind to address\n");

    for stream in listener.incoming(){
        match stream {
            Ok(stream) => {
                handle_connection(stream);
            }
            Err(err) => {
                println!("Error: {}", err);
                break;
            }
        }
    }
    Ok(())
}
