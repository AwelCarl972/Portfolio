//! Détection des entités sensibles + empreinte HMAC-SHA256 déterministe.
//!
//! Strictement équivalent au moteur Python (`infrastructure/privacy/pseudonymizer.py`) : mêmes motifs,
//! même normalisation, même empreinte. Un test croisé (pytest) vérifie que les deux moteurs produisent
//! exactement le même texte anonymisé.
//!
//! Le binaire renvoie des segments ordonnés (texte en clair OU entité + empreinte) plutôt que des offsets :
//! on évite toute ambiguïté octets (Rust) / caractères (Python). Python choisit ensuite la longueur
//! d'alias en consultant sa table de correspondance (gestion des collisions).

use fancy_regex::Regex;
use hmac::{Hmac, Mac};
use serde::{Deserialize, Serialize};
use sha2::Sha256;

#[derive(Deserialize)]
pub struct Entity {
    pub kind: String,
    pub value: String,
}

#[derive(Deserialize)]
pub struct Request {
    pub text: String,
    pub key_hex: String,
    #[serde(default)]
    pub catalog: Vec<Entity>,
}

#[derive(Serialize)]
#[serde(untagged)]
pub enum Segment {
    Plain { text: String },
    Entity { kind: String, original: String, digest: String },
}

const COMMUNES: [&str; 24] = [
    "Saint-Denis", "Sainte-Marie", "Sainte-Suzanne", "Saint-André", "Bras-Panon", "Saint-Benoît",
    "Sainte-Rose", "Plaine-des-Palmistes", "Saint-Pierre", "Saint-Louis", "Saint-Paul", "Le Port",
    "La Possession", "Saint-Leu", "Les Avirons", "L'Étang-Salé", "Saint-Joseph", "Petite-Île",
    "Le Tampon", "Entre-Deux", "Cilaos", "Salazie", "Trois-Bassins", "Saint-Philippe",
];

/// Motifs génériques, dans le même ordre que côté Python.
fn patterns() -> Vec<(&'static str, Regex)> {
    let communes = COMMUNES.iter().map(|c| fancy_regex::escape(c).into_owned()).collect::<Vec<_>>().join("|");
    [
        ("MAIL", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+".to_string()),
        ("TEL", r"(?<!\w)(?:\+262\s?|0)[26]\d{2}(?:[ .]?\d{2}){3}(?!\d)".to_string()),
        ("ACTIF", r"\b[A-Z]{2}-\d{3}-[A-Z]{2}\b".to_string()),
        ("ACTIF", r"\bSN-[A-Z]{2}-\d{4,}\b".to_string()),
        ("REF", r"\b(?:OT|BC|DOS)-\d{3,}\b".to_string()),
        ("LIEU", r"\b\d{1,3}(?:\s?bis)?\s+(?:rue|chemin|route|avenue|impasse|allée|boulevard)\s+[^,.;\n]{3,45}".to_string()),
        ("LIEU", format!(r"(?<!\w)(?:{communes})(?!\w)")),
    ]
    .into_iter()
    .map(|(k, p)| (k, Regex::new(&format!("(?i){p}")).expect("motif valide")))
    .collect()
}

/// Même normalisation que Python : espaces compactés + minuscules.
pub fn norm(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase()
}

fn digest(key: &[u8], kind: &str, original: &str) -> String {
    let mut mac = Hmac::<Sha256>::new_from_slice(key).expect("clé HMAC");
    mac.update(format!("{kind}|{}", norm(original)).as_bytes());
    hex::encode_upper(mac.finalize().into_bytes())
}

struct Span {
    start: usize,
    end: usize,
    kind: String,
    original: String,
}

pub fn run(req: &Request) -> Result<Vec<Segment>, String> {
    let key = hex::decode(&req.key_hex).map_err(|e| format!("clé hexadécimale invalide : {e}"))?;
    let text = &req.text;
    let mut spans: Vec<Span> = Vec::new();

    // 1. Dictionnaire des entités connues (prioritaire, plus long d'abord), valeur canonique conservée
    let mut ents: Vec<&Entity> = req.catalog.iter().filter(|e| !e.value.trim().is_empty()).collect();
    ents.sort_by_key(|e| std::cmp::Reverse(e.value.chars().count()));
    if !ents.is_empty() {
        let alt = ents.iter().map(|e| fancy_regex::escape(&e.value).into_owned()).collect::<Vec<_>>().join("|");
        let rx = Regex::new(&format!(r"(?i)(?<!\w)(?:{alt})(?!\w)")).map_err(|e| e.to_string())?;
        for m in rx.find_iter(text) {
            let m = m.map_err(|e| e.to_string())?;
            let found = norm(m.as_str());
            if let Some(e) = ents.iter().find(|e| norm(&e.value) == found) {
                spans.push(Span { start: m.start(), end: m.end(), kind: e.kind.clone(), original: e.value.clone() });
            }
        }
    }
    // 2. Motifs génériques
    for (kind, rx) in patterns() {
        for m in rx.find_iter(text) {
            let m = m.map_err(|e| e.to_string())?;
            let original = m.as_str().split_whitespace().collect::<Vec<_>>().join(" ");
            spans.push(Span { start: m.start(), end: m.end(), kind: kind.to_string(), original });
        }
    }
    // 3. Chevauchements : le plus à gauche puis le plus long gagne (tri stable, comme Python)
    spans.sort_by(|a, b| a.start.cmp(&b.start).then((b.end - b.start).cmp(&(a.end - a.start))));

    let mut out = Vec::new();
    let (mut pos, mut last_end) = (0usize, 0usize);
    for s in spans {
        if s.start < last_end {
            continue;
        }
        if s.start > pos {
            out.push(Segment::Plain { text: text[pos..s.start].to_string() });
        }
        let d = digest(&key, &s.kind, &s.original);
        out.push(Segment::Entity { kind: s.kind, original: s.original, digest: d });
        pos = s.end;
        last_end = s.end;
    }
    if pos < text.len() {
        out.push(Segment::Plain { text: text[pos..].to_string() });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(text: &str) -> Request {
        Request { text: text.into(), key_hex: hex::encode([7u8; 32]), catalog: vec![Entity { kind: "CLIENT".into(), value: "Payet Express".into() }] }
    }

    fn rebuild(segs: &[Segment]) -> String {
        segs.iter().map(|s| match s { Segment::Plain { text } => text.clone(), Segment::Entity { original, .. } => original.clone() }).collect()
    }

    #[test]
    fn normalise_espaces_et_casse() {
        assert_eq!(norm("  Le   PORT \n"), "le port");
    }

    #[test]
    fn detecte_et_preserve_le_texte() {
        let text = "Payet Express : camion FG-482-RT au Port, tél. 0692 11 47 23, à Saint-Pierre.";
        let segs = run(&req(text)).unwrap();
        let kinds: Vec<&str> = segs.iter().filter_map(|s| match s { Segment::Entity { kind, .. } => Some(kind.as_str()), _ => None }).collect();
        assert_eq!(kinds, ["CLIENT", "ACTIF", "TEL", "LIEU"]);
        assert_eq!(rebuild(&segs), text); // aucun caractère perdu, accents compris
    }

    #[test]
    fn empreinte_deterministe_et_dependante_de_la_cle() {
        let a = digest(&[1; 32], "ACTIF", "FG-482-RT");
        assert_eq!(a, digest(&[1; 32], "ACTIF", "fg-482-rt"));
        assert_ne!(a, digest(&[2; 32], "ACTIF", "FG-482-RT"));
    }
}
