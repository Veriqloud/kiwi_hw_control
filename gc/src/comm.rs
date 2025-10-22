use std::fmt::Debug;
use std::io::prelude::*;
use std::net::TcpStream;
use std::os::unix::net::UnixStream;

// Messages from Alice to Bob
#[derive(Debug)]
pub enum HwControl {
    InitDdr = 1,
    SyncAtPps = 2,
}

impl From<u8> for HwControl {
    fn from(value: u8) -> Self {
        const INITDDR: u8 = HwControl::InitDdr as u8;
        const SYNCATPPS: u8 = HwControl::SyncAtPps as u8;
        match value {
            INITDDR => HwControl::InitDdr,
            SYNCATPPS => HwControl::SyncAtPps,
            _ => panic!("Byte cannot be converted to HwControl"),
        }
    }
}

// ToByte required by trait Comm
pub trait ToByte {
    fn tobyte(self) -> u8;
}

impl ToByte for HwControl {
    fn tobyte(self) -> u8 {
        self as u8
    }
}

// custom send and recv for single byte messages
pub trait Comm {
    fn send<T: ToByte + From<u8> + Debug>(&mut self, message: T) -> std::io::Result<()>;
    fn recv<T: ToByte + From<u8> + Debug>(&mut self) -> std::io::Result<T>;
}

impl Comm for UnixStream {
    fn send<T: ToByte + From<u8> + Debug>(&mut self, message: T) -> std::io::Result<()> {
        println!("[gc-comm] UNIX SEND: {:?}", message);
        let m_b = message.tobyte();
        self.write(&[m_b])?;
        Ok(())
    }
    fn recv<T: ToByte + From<u8> + Debug>(&mut self) -> std::io::Result<T> {
        let mut m_b: [u8; 1] = [0];
        self.read(&mut m_b)?;
        let message = T::from(m_b[0]);
        println!("[gc-comm] UNIX RECV: {:?}", message);
        Ok(message)
    }
}

impl Comm for TcpStream {
    fn send<T: ToByte + From<u8> + Debug>(&mut self, message: T) -> std::io::Result<()> {
        println!("[gc-comm] TCP SEND: {:?}", message);
        let m_b = message.tobyte();
        self.write(&[m_b])?;
        Ok(())
    }
    fn recv<T: ToByte + From<u8> + Debug>(&mut self) -> std::io::Result<T> {
        let mut m_b: [u8; 1] = [0];
        let l = self.read(&mut m_b)?;
        // if you hit ctrl-c on Alice, read returns without error and length 0; we make an error
        // out of this
        if l == 0 {
            let myerror = std::io::Error::new(std::io::ErrorKind::Other, "connection closed");
            return Err(myerror);
        }
        let message = T::from(m_b[0]);
        println!("[gc-comm] TCP RECV: {:?}", message);
        Ok(message)
    }
}

