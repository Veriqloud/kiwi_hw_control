use std::net::TcpStream;
use serde::{Serialize, Deserialize};
use std::io::prelude::*;
use std::io;



#[derive(Serialize, Deserialize, Debug)]
pub enum MessageHeader{
    Start,
    Angles,
    Done,
    Error
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Message{
    pub header: MessageHeader,
    pub body: Vec<u32>
}

impl Message {
    pub fn snd(&self, stream: &mut TcpStream){
        let encode: Vec<u8> = bincode::serialize(&self).unwrap();
        let l = (encode.len() as u32).to_be_bytes();
        stream.write_all(&l).expect("could not write length into stream");
        stream.write_all(&encode).expect("could not write message into stream");
    }
}

pub fn rcv(stream: &mut TcpStream) -> io::Result<Message> {
    let mut buf = [0u8; 4];
    stream.read_exact(&mut buf)?;
    let l = u32::from_be_bytes(buf);
    let mut buf = vec![0;l as usize];
    stream.read_exact(&mut buf).expect("could not read stream for message");
    let message : Message = bincode::deserialize(&buf).expect("could not deserialize message");
    return Ok(message);
}



//pub fn add(left: usize, right: usize) -> usize {
//    left + right
//}
//
//#[cfg(test)]
//mod tests {
//    use super::*;
//
//    #[test]
//    fn it_works() {
//        let result = add(2, 2);
//        assert_eq!(result, 4);
//    }
//}
