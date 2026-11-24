//! datakit — outils data natifs du portfolio.
//!
//!   datakit anonymize   < requête JSON (stdin)  > segments JSON (stdout)
//!   datakit profile <fichier.csv[.gz]>...        > profil qualité JSON (stdout)
//!
//! Le binaire ne lit ni n'écrit aucune base : il reçoit tout ce qu'il lui faut et répond en JSON.
//! Python (couche infrastructure) reste maître du stockage de la table de correspondance.

mod anonymize;
mod profile;

use std::io::{self, Read, Write};
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("anonymize") => run_anonymize(),
        Some("profile") if args.len() > 1 => profile::run(&args[1..]),
        _ => Err("usage : datakit anonymize < requete.json | datakit profile <fichier>...".to_string()),
    };
    match result {
        Ok(json) => {
            let mut out = io::stdout().lock();
            let _ = out.write_all(json.as_bytes());
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("datakit : {e}");
            ExitCode::FAILURE
        }
    }
}

fn run_anonymize() -> Result<String, String> {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).map_err(|e| e.to_string())?;
    let req: anonymize::Request = serde_json::from_str(&input).map_err(|e| format!("JSON invalide : {e}"))?;
    let segments = anonymize::run(&req)?;
    serde_json::to_string(&segments).map_err(|e| e.to_string())
}
