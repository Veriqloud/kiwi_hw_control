use std::net::TcpStream;
use serde::{Serialize, Deserialize};
use std::io::prelude::*;
use std::io;
use std::fs::File;
use itertools::izip;
//use std::io::prelude::*;



#[derive(Serialize, Deserialize, Debug)]
pub enum MessageHeader{
    Start,
    Angles,
    Results,
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
    let message : Message = bincode::deserialize(&buf)
        .expect("could not deserialize message");
    return Ok(message);
}


pub fn read_angles(fifo: &mut File, chunks_to_read: usize) -> io::Result<Vec<u32>>{
    let mut buf = [0;16];
    let capacity = chunks_to_read*4;
    let mut angles = Vec::<u32>::with_capacity(capacity);
    while angles.len()<capacity {
        fifo.read_exact(&mut buf)
            .expect("error reading fifo");
        for i in 0..4 {
            let buf32 = u32::from_be_bytes(buf[i..i+4]
                .try_into().unwrap());
            angles.push(buf32);
        }
    }
    return Ok(angles);
}

fn count_errors(a1: u32, a2: u32, r: u32) -> (u32,u32){
    let basis_mask = 0b01010101010101010101010101010101;
    let basis_match = !(a1 ^ a2);
    let basis_match_masked = basis_match & basis_mask;

    let num_basis_match = basis_match_masked.count_ones();

    let a2_flipped = a2 ^ r;

    let a1_masked = a1 & (basis_match_masked<<1);
    let a2_masked = a2_flipped & (basis_match_masked<<1);

    //let a2_masked_flipped = a2_masked ^ r;

    let errors = a1_masked ^ a2_masked;
    let num_errors = errors.count_ones();

    return (num_errors, num_basis_match)
}

pub fn calc_qber(angles1: Vec<u32>, angles2: Vec<u32>, result: Vec<u32>) -> f64 {
    let mut num_basis_match = 0;
    let mut num_errors = 0;
    for (a1,a2,r) in izip!(&angles1, &angles2, &result){
        let (e,b) = count_errors(*a1, *a2, *r);
        num_basis_match += b;
        num_errors += e;
    }

    let qber:f64 = num_errors as f64 /num_basis_match as f64;

    return qber;
}







//pub fn add(left: usize, right: usize) -> usize {
//    left + right
//}
//
#[cfg(test)]
mod tests {
    use super::*;
    use rand::prelude::*;

    #[test]
    fn qber() {
        let qber = 0.05;
        let mut rng = rand::thread_rng();
        let mut angles1: Vec<u32> = vec![];
        let mut angles2: Vec<u32> = vec![];
        let mut result: Vec<u32> = vec![];
        for i in 0..10000{
            let mut a1: u32 = 0;
            let mut a2: u32 = 0;
            let mut rr: u32 = 0;
            for i in 0..16{
                let basis1: u32 = rng.gen_bool(0.5).try_into().unwrap();
                let basis2: u32 = rng.gen_bool(0.5).try_into().unwrap();
                let s1: u32 = rng.gen_bool(0.5).try_into().unwrap();
                let s2: u32 = rng.gen_bool(0.5).try_into().unwrap();

                let mut r: u32 = 0;

                if basis1==basis2 {
                    if s1==s2 {r=0}
                    else {r=1}
                    if rng.gen_bool(qber) {r = (!r) & 1}
                } else {r = rng.gen_bool(0.5).try_into().unwrap()}
                
                let comb1 = (s1 << 1) + basis1;
                let comb2 = (s2 << 1) + basis2;
                let combr = r << 1;
                a1 = a1.checked_add(comb1 << (i*2)).unwrap();
                a2 = a2.checked_add(comb2 << (i*2)).unwrap();
                rr = rr.checked_add(combr << (i*2)).unwrap();
            }
            angles1.push(a1);
            angles2.push(a2);
            result.push(rr);
        }

        let qber_test = calc_qber(angles1, angles2, result);

        println!("qber_test {:?}", qber_test);
        
        assert!((qber_test-qber).abs() < 0.001);
    }
}







