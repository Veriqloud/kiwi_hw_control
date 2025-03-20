use std::net::TcpStream;
use serde::{Serialize, Deserialize};
use std::io::prelude::*;
use std::io;
//use std::fs::File;
//use itertools::izip;
//use std::io::prelude::*;


// Messages from node to gc_client
#[derive(Debug)]
pub enum ControlMessage{
    Start,
    Stop,
    Acknnowledged
}


#[derive(Serialize, Deserialize, Debug)]
pub enum MessageHeader{
    InitDdr,
    SyncAtPps,
    TranferGc,
    Done,
    Error,
    Exit
}

// Messages between gc_client and gc_server
#[derive(Serialize, Deserialize, Debug)]
pub struct Message{
    pub header: MessageHeader,
    pub body: Vec<u64>
}

impl Message {
    pub fn snd(&self, stream: &mut TcpStream){
        let encode: Vec<u8> = bincode::serialize(&self).unwrap();
        let l = (encode.len() as u32).to_le_bytes();
        stream.write_all(&l).expect("could not write length into stream");
        stream.write_all(&encode).expect("could not write message into stream");
    }
}

pub fn rcv(stream: &mut TcpStream) -> io::Result<Message> {
    let mut buf = [0u8; 4];
    stream.read_exact(&mut buf)?;
    let l = u32::from_le_bytes(buf);
    let mut buf = vec![0;l as usize];
    stream.read_exact(&mut buf).expect("could not read stream for message");
    let message : Message = bincode::deserialize(&buf)
        .expect("could not deserialize message");
    return Ok(message);
}


//pub fn read_angles(fifo: &mut File, chunks_to_read: usize) -> io::Result<Vec<u32>>{
//    let mut buf = [0;16];
//    let capacity = chunks_to_read*4;
//    let mut angles = Vec::<u32>::with_capacity(capacity);
//    while angles.len()<capacity {
//        fifo.read_exact(&mut buf)
//            .expect("error reading fifo");
//        for i in 0..4 {
//            let buf32 = u32::from_le_bytes(buf[i..i+4]
//                .try_into().unwrap());
//            angles.push(buf32);
//        }
//    }
//    return Ok(angles);
//}




#[cfg(test)]
mod tests {
    use super::*;
    use rand::prelude::*;

    #[test]
    fn qber() {
        let qber = 0.05;
        assert!(qber == 0.05);
    }
}







