//! Profilage qualité des fichiers bruts : lecture en flux (gzip transparent), une passe par fichier.
//!
//! Pour chaque colonne : taux de valeurs vides, cardinalité (exacte jusqu'à 10 000 valeurs distinctes),
//! type déduit (entier, décimal, date, booléen, texte), min/max numériques. Pour chaque fichier : lignes,
//! lignes mal formées (nombre de champs incorrect), temps de traitement.

use flate2::read::GzDecoder;
use serde::Serialize;
use std::collections::HashSet;
use std::fs::File;
use std::io::{BufReader, Read};
use std::path::Path;
use std::time::Instant;

const DISTINCT_CAP: usize = 10_000;

#[derive(Serialize)]
struct ColumnProfile {
    name: String,
    inferred_type: &'static str,
    null_pct: f64,
    distinct: usize,
    distinct_capped: bool,
    min: Option<f64>,
    max: Option<f64>,
}

#[derive(Serialize)]
struct FileProfile {
    file: String,
    size_kb: u64,
    rows: u64,
    malformed_rows: u64,
    columns: usize,
    null_cells_pct: f64,
    elapsed_ms: f64,
    column_profiles: Vec<ColumnProfile>,
}

#[derive(Default)]
struct Acc {
    nulls: u64,
    ints: u64,
    floats: u64,
    dates: u64,
    bools: u64,
    texts: u64,
    min: Option<f64>,
    max: Option<f64>,
    distinct: HashSet<String>,
    capped: bool,
}

fn is_date(v: &str) -> bool {
    let b = v.as_bytes();
    b.len() >= 10 && b[4] == b'-' && b[7] == b'-' && b[..4].iter().chain(&b[5..7]).chain(&b[8..10]).all(u8::is_ascii_digit)
}

impl Acc {
    fn push(&mut self, raw: &str) {
        let v = raw.trim();
        if v.is_empty() {
            self.nulls += 1;
            return;
        }
        if let Ok(i) = v.parse::<i64>() {
            self.ints += 1;
            self.num(i as f64);
        } else if let Ok(f) = v.parse::<f64>() {
            self.floats += 1;
            self.num(f);
        } else if is_date(v) {
            self.dates += 1;
        } else if matches!(v.to_ascii_lowercase().as_str(), "true" | "false") {
            self.bools += 1;
        } else {
            self.texts += 1;
        }
        if !self.capped {
            self.distinct.insert(v.to_string());
            self.capped = self.distinct.len() >= DISTINCT_CAP;
        }
    }
    fn num(&mut self, x: f64) {
        self.min = Some(self.min.map_or(x, |m| m.min(x)));
        self.max = Some(self.max.map_or(x, |m| m.max(x)));
    }
    fn inferred(&self) -> &'static str {
        let filled = self.ints + self.floats + self.dates + self.bools + self.texts;
        if filled == 0 {
            "vide"
        } else if self.texts > 0 {
            "texte"
        } else if self.dates == filled {
            "date"
        } else if self.bools == filled {
            "booléen"
        } else if self.floats > 0 {
            "décimal"
        } else {
            "entier"
        }
    }
}

fn profile_file(path: &str) -> Result<FileProfile, String> {
    let t0 = Instant::now();
    let f = File::open(path).map_err(|e| format!("{path} : {e}"))?;
    let size_kb = f.metadata().map(|m| m.len() / 1024).unwrap_or(0);
    let reader: Box<dyn Read> = if path.ends_with(".gz") {
        Box::new(GzDecoder::new(BufReader::new(f)))
    } else {
        Box::new(BufReader::new(f))
    };
    let mut rdr = csv::ReaderBuilder::new().delimiter(b';').flexible(true).from_reader(reader);
    let headers: Vec<String> = rdr.headers().map_err(|e| e.to_string())?.iter().map(str::to_string).collect();
    let mut accs: Vec<Acc> = headers.iter().map(|_| Acc::default()).collect();
    let (mut rows, mut malformed) = (0u64, 0u64);
    let mut record = csv::StringRecord::new();
    while rdr.read_record(&mut record).map_err(|e| e.to_string())? {
        rows += 1;
        if record.len() != headers.len() {
            malformed += 1;
        }
        for (acc, v) in accs.iter_mut().zip(record.iter()) {
            acc.push(v);
        }
    }
    let total_nulls: u64 = accs.iter().map(|a| a.nulls).sum();
    let cells = rows * headers.len() as u64;
    let pct = |n: u64, d: u64| if d == 0 { 0.0 } else { (1000.0 * n as f64 / d as f64).round() / 10.0 };
    let column_profiles = headers
        .into_iter()
        .zip(&accs)
        .map(|(name, a)| ColumnProfile {
            name,
            inferred_type: a.inferred(),
            null_pct: pct(a.nulls, rows),
            distinct: a.distinct.len(),
            distinct_capped: a.capped,
            min: a.min,
            max: a.max,
        })
        .collect::<Vec<_>>();
    Ok(FileProfile {
        file: Path::new(path).file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
        size_kb,
        rows,
        malformed_rows: malformed,
        columns: column_profiles.len(),
        null_cells_pct: pct(total_nulls, cells),
        elapsed_ms: (t0.elapsed().as_secs_f64() * 10_000.0).round() / 10.0,
        column_profiles,
    })
}

pub fn run(paths: &[String]) -> Result<String, String> {
    let profiles = paths.iter().map(|p| profile_file(p)).collect::<Result<Vec<_>, _>>()?;
    serde_json::to_string(&profiles).map_err(|e| e.to_string())
}
