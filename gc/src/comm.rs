use std::net::TcpStream;
use std::io::prelude::*;
//use std::io;
use clap::ValueEnum;
use std::os::unix::net::UnixStream;
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

// Messages from gc_client to node
#[derive(Debug)]
pub enum Response{
    Done = 1,
    DidNothing = 2,
    //Idle = 2,
    //Running = 3
}

// Messages from Alice to Bob
#[derive(Debug)]
pub enum HwControl{
    InitDdr = 1,
    SyncAtPps = 2,
    SendGc = 3,
}


// construct message from single byte
impl From<u8> for Request{
    fn from(value: u8) -> Self {
        const START: u8 = Request::Start as u8;
        const STOP: u8 = Request::Stop as u8;
        const STATUS: u8 = Request::Status as u8;
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
        const DIDNOTHING: u8 = Response::DidNothing as u8;
        //const RUNNING: u8 = Response::Running as u8;
        match value {
            DONE => Response::Done,
            DIDNOTHING => Response::DidNothing,
            //RUNNING => Response::Running,
            _ => panic!("Byte cannot be converted to Response")
        }
    }
}

impl From<u8> for HwControl{
    fn from(value: u8) -> Self {
        const INITDDR: u8 = HwControl::InitDdr as u8;
        const SYNCATPPS: u8 = HwControl::SyncAtPps as u8;
        const SENDGC: u8 = HwControl::SendGc as u8;
        match value {
            INITDDR => HwControl::InitDdr,
            SYNCATPPS => HwControl::SyncAtPps,
            SENDGC => HwControl::SendGc,
            _ => panic!("Byte cannot be converted to HwControl")
        }
    }
}

// ToByte required by trait Comm
pub trait ToByte{
    fn tobyte(self) -> u8;
}

impl ToByte for Request{
    fn tobyte(self) -> u8{ self as u8 }
}
impl ToByte for Response{
    fn tobyte(self) -> u8{ self as u8 }
}
impl ToByte for HwControl{
    fn tobyte(self) -> u8{ self as u8 }
}


// custom send and recv for single byte messages
pub trait Comm{
    fn send<T: ToByte + From<u8>>(&mut self, message: T) -> std::io::Result<()>;
    fn recv<T: ToByte + From<u8>>(&mut self) -> std::io::Result<T>;
}

impl Comm for UnixStream{
    fn send<T: ToByte + From<u8>>(&mut self, message: T) -> std::io::Result<()> {
        let m_b = message.tobyte();
        self.write(&[m_b])?;
        Ok(())
    }
    fn recv<T: ToByte + From<u8>>(&mut self) -> std::io::Result<T>{
        let mut m_b : [u8;1] = [0];
        self.read(&mut m_b)?;
        let message = T::from(m_b[0]);
        Ok(message)
    }
}

impl Comm for TcpStream{
    fn send<T: ToByte + From<u8>>(&mut self, message: T) -> std::io::Result<()> {
        let m_b = message.tobyte();
        self.write(&[m_b])?;
        Ok(())
    }
    fn recv<T: ToByte + From<u8>>(&mut self) -> std::io::Result<T>{
        let mut m_b : [u8;1] = [0];
        self.read(&mut m_b)?;
        let message = T::from(m_b[0]);
        Ok(message)
    }
}










