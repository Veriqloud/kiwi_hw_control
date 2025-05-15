use std::net::TcpStream;
use std::io::prelude::*;
use std::os::unix::net::UnixStream;
use clap::ValueEnum;

// Messages from node to gc_client
#[derive(Debug, Clone, ValueEnum)]
pub enum Request{
    Start = 1,
    Stop = 2,
    DebugOn = 3
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
pub enum Qber{
    SendAngles = 4,
}


// construct message from single byte
impl From<u8> for Request{
    fn from(value: u8) -> Self {
        const START: u8 = Request::Start as u8;
        const STOP: u8 = Request::Stop as u8;
        const DEBUGON: u8 = Request::DebugOn as u8;
        match value {
            START => Request::Start,
            STOP => Request::Stop,
            DEBUGON => Request::DebugOn,
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


impl From<u8> for Qber{
    fn from(value: u8) -> Self {
        const SENDANGLES: u8 = Qber::SendAngles as u8;
        match value {
            SENDANGLES => Qber::SendAngles,
            _ => panic!("Byte cannot be converted to Qber message")
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
impl ToByte for Qber{
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
        let l = self.read(&mut m_b)?;
        // if you hit ctrl-c on Alice, read returns without error and length 0; we make an error
        // out of this
        if l==0 { 
            let myerror = std::io::Error::new(std::io::ErrorKind::Other, "connection closed");
            return Err(myerror)
        }
        let message = T::from(m_b[0]);
        Ok(message)
    }
}









