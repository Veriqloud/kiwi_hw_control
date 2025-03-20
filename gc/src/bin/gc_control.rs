use clap::{Parser};
use gc::ControlMessage;








#[derive(Parser)]
struct Cli {
    /// message to send
    message: String,
}


fn main() -> std::io::Result<()> {
    
    let cli = Cli::parse();
    println!{"cli: {:?}", cli.message};


    Ok(())
}






