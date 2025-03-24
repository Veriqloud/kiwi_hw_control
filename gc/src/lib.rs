use std::net::TcpStream;
use serde::{Serialize, Deserialize};
use std::io::prelude::*;
use std::io;
use clap::ValueEnum;
//use std::fs::File;
//use itertools::izip;
//use std::io::prelude::*;


// Messages from node to gc_client
#[derive(Debug, Clone, ValueEnum)]
pub enum Request{
    Start = 1,
    Stop = 2,
    Status = 3
}

#[derive(Debug)]
pub enum Response{
    Done = 1,
    Idle = 2,
    Running = 3
}

impl From<u8> for Request{
    fn from(value: u8) -> Self {
        const START: u8 = Request::Start as u8;
        const STOP: u8 = Request::Stop as u8;
        const Status: u8 = Request::Status as u8;
        match value {
            START => Request::Start,
            STOP => Request::Stop,
            STATUS => Request::Status,
            _ => panic!("Byte cannot be converted to Request")
        }
    }
}

impl From<u8> for Response{
    fn from(value: u8) -> Self {
        const DONE: u8 = Response::Done as u8;
        const IDLE: u8 = Response::Idle as u8;
        const RUNNING: u8 = Response::Running as u8;
        match value {
            DONE => Response::Done,
            IDLE => Response::Idle,
            RUNNING => Response::Running,
            _ => panic!("Byte cannot be converted to Response")
        }
    }
}


#[derive(Debug)]
pub enum HwControl{
    InitDdr = 1,
    SyncAtPps = 2,
}

impl From<u8> for HwControl{
    fn from(value: u8) -> Self {
        const INITDDR: u8 = Response::InitDdr as u8;
        const SYNCATPPS: u8 = Response::SyncAtPps as u8;
        match value {
            INITDDR => Response::InitDdr,
            SYNCATPPS => Response::SyncAtPps,
            _ => panic!("Byte cannot be converted to Response")
        }
    }
}

impl Write<&TcpStream> for HwControl{
    fn write(Self, &mut stream: TcpStream) -> Result<()> {
        let buf = Self as u8;
        stream.write()
        Ok()
    }
}



//#[derive(Serialize, Deserialize, Debug)]
//pub enum MessageHeader{
//    InitDdr,
//    SyncAtPps,
//    TranferGc,
//    Done,
//    Stop,
//    Error,
//    Exit
//}
//
//// Messages between gc_client and gc_server
//#[derive(Serialize, Deserialize, Debug)]
//pub struct Message{
//    pub header: MessageHeader,
//    pub body: Vec<u64>
//}
//
//impl Message {
//    pub fn snd(&self, stream: &mut TcpStream){
//        let encode: Vec<u8> = bincode::serialize(&self).unwrap();
//        let l = (encode.len() as u32).to_le_bytes();
//        stream.write_all(&l).expect("could not write length into stream");
//        stream.write_all(&encode).expect("could not write message into stream");
//    }
//}
//
//pub fn rcv(stream: &mut TcpStream) -> io::Result<Message> {
//    let mut buf = [0u8; 4];
//    stream.read_exact(&mut buf)?;
//    let l = u32::from_le_bytes(buf);
//    let mut buf = vec![0;l as usize];
//    stream.read_exact(&mut buf).expect("could not read stream for message");
//    let message : Message = bincode::deserialize(&buf)
//        .expect("could not deserialize message");
//    return Ok(message);
//}



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
    fn plen() {
        let qber = 0.05;
        assert!(qber == 0.05);
    }
}







