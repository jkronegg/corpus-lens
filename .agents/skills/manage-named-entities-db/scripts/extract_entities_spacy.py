#!/usr/bin/env python3
"""
extract_entities_spacy.py — Extrait les entités nommées (personnes) d'un fichier Markdown.

Utilise spaCy pour la NER (Named Entity Recognition) en français et allemand.
Affiche les personnes détectées par page et ligne, avec score de confiance.

Usage:
    python -u extract_entities_spacy.py path/to/document.md
    python -u extract_entities_spacy.py path/to/document.md --lang fr --min-confidence 0.5
    python -u extract_entities_spacy.py path/to/document.md --insert  # insère dans la BD

Dépendances:
    pip install spacy
    python -m spacy download fr_core_news_lg
    python -m spacy download de_core_news_lg
"""

import argparse
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    import spacy
except ImportError:
    print("Erreur : spacy n'est pas installé.", file=sys.stderr)
    print("Installez avec : pip install spacy", file=sys.stderr)
    print("Puis : python -m spacy download fr_core_news_lg de_core_news_lg", file=sys.stderr)
    sys.exit(1)

try:
    from rapidfuzz import fuzz as _fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _fuzz = None
    _RAPIDFUZZ_AVAILABLE = False

# Importe le module db pour insertion optionnelle
sys.path.insert(0, str(Path(__file__).parent))
from db import add_mention, search_person, source_has_mentions, upsert_person, get_connection, delete_mentions_for_source

# ---------------------------------------------------------------------------
# Configuration spaCy
# ---------------------------------------------------------------------------
SPACY_MODELS = {
    "fr": "fr_core_news_lg",
    "de": "de_core_news_lg",
}


def _append_to_log(log_file: str | Path | None, message: str) -> None:
    if not log_file:
        return
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _emit(message: str, *, quiet: bool = False, log_file: str | Path | None = None) -> None:
    if not quiet:
        print(message)
    _append_to_log(log_file, message)


@lru_cache(maxsize=None)
def _load_spacy_model_cached(lang: str):
    """Charge (et met en cache) le modèle spaCy pour la langue donnée."""
    model_name = SPACY_MODELS.get(lang)
    if not model_name:
        raise ValueError(f"Langue non supportée: {lang}. Supportées: {list(SPACY_MODELS.keys())}")

    try:
        nlp = spacy.load(model_name)
    except OSError:
        print(
            f"Erreur : modèle {model_name} non trouvé.",
            file=sys.stderr,
        )
        print(
            f"Téléchargez avec : python -m spacy download {model_name}",
            file=sys.stderr,
        )
        sys.exit(1)

    return nlp


def load_spacy_model(lang: str, *, quiet: bool = False, log_file: str | Path | None = None):
    """Charge le modèle spaCy avec cache, sans inclure le mode verbeux dans la clé de cache."""
    model_name = SPACY_MODELS.get(lang)
    if not model_name:
        raise ValueError(f"Langue non supportée: {lang}. Supportées: {list(SPACY_MODELS.keys())}")

    before = _load_spacy_model_cached.cache_info().misses
    nlp = _load_spacy_model_cached(lang)
    after = _load_spacy_model_cached.cache_info().misses
    if after > before:
        _emit(
            f"[extract_entities] Chargement du modèle spaCy (premier chargement du processus) : {model_name}",
            quiet=quiet,
            log_file=log_file,
        )
    return nlp


# ---------------------------------------------------------------------------
# Clustering fuzzy : regroupe les aliases au sein d'un même document
# ---------------------------------------------------------------------------
_TITLES = re.compile(
    r"^(g[eé]n[eé]ral|generalmajor|colonel|dr\.?|prof\.?|m\.?|mme\.?|sr\.?|jr\.?|monsieur|messieurs|président|von|de|van|du)\s+",
    re.IGNORECASE,
)

_PERSON_STOPWORDS = {
    "messieurs",
    "monsieur",
    "madame",
    "mesdames",
    "mme",
    "mademoiselle",
    "président",
    "president",
    "présidente",
    "presidente",
}


def _normalize_for_cluster(name: str) -> str:
    """Retire titres/particules pour comparaison."""
    return _TITLES.sub("", name.strip()).lower()


def _is_suffix_match(short: str, long: str) -> bool:
    """
    Vérifie si les tokens de `short` sont un suffixe de tokens de `long`.
    Ex: "Wille" ∈ suffixe de "Ulrich Wille" → True
        "Moritz von Wattenwyl" ∈ suffixe de "Friedrich Moritz von Wattenwyl" → True
    """
    tokens_long = _normalize_for_cluster(long).split()
    tokens_short = _normalize_for_cluster(short).split()
    if not tokens_short or len(tokens_short) >= len(tokens_long):
        return False
    return tokens_long[-len(tokens_short):] == tokens_short


def _fuzzy_score(a: str, b: str) -> float:
    """Score de similarité 0–100 entre deux noms normalisés."""
    if _RAPIDFUZZ_AVAILABLE and _fuzz is not None:
        return _fuzz.token_set_ratio(
            _normalize_for_cluster(a),
            _normalize_for_cluster(b),
        )
    # Fallback sans rapidfuzz : ratio de tokens communs
    ta = set(_normalize_for_cluster(a).split())
    tb = set(_normalize_for_cluster(b).split())
    if not ta or not tb:
        return 0.0
    return 100.0 * len(ta & tb) / max(len(ta), len(tb))


def cluster_names(names: list, fuzzy_threshold: float = 85.0) -> list:
    """
    Regroupe une liste de noms en clusters d'aliases au sein d'un même document.

    Stratégie (par ordre de priorité) :
    1. Suffixe de tokens : "Wille" → "Ulrich Wille"
    2. Fuzzy token_set_ratio ≥ fuzzy_threshold

    Retourne une liste de clusters :
    [
        {"canonical": "Ulrich Wille", "aliases": ["Wille", "général Wille"]},
        ...
    ]
    Seuls les clusters avec au moins 1 alias sont inclus.
    """
    sorted_names = sorted(set(names), key=lambda n: len(n.split()), reverse=True)

    # Union-Find
    parent: dict = {n: n for n in sorted_names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _canonical_rank(name: str) -> tuple[int, int, int, str]:
        """
        Plus petit = meilleur candidat canonique.
        Priorités:
        1) éviter les formes titrées ("Monsieur Fazy")
        2) privilégier plus de tokens normalisés ("Ulrich Wille" > "Wille")
        3) à égalité, préférer moins de tokens bruts
        """
        has_title = 0 if _TITLES.match(name.strip()) else 1
        norm_tokens = len(_normalize_for_cluster(name).split())
        raw_tokens = len(name.split())
        return (-has_title, -norm_tokens, raw_tokens, name.lower())

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Choix du canonique basé sur une heuristique linguistique
        # (évite de garder "Monsieur X" comme nom principal).
        if _canonical_rank(ra) <= _canonical_rank(rb):
            parent[rb] = ra
        else:
            parent[ra] = rb

    for i, a in enumerate(sorted_names):
        for b in sorted_names[i + 1:]:
            longer, shorter = (a, b) if len(a) >= len(b) else (b, a)
            if _is_suffix_match(shorter, longer):
                union(longer, shorter)
            elif _fuzzy_score(a, b) >= fuzzy_threshold:
                union(a, b)

    # Reconstruction des clusters
    clusters_map: dict = {}
    for name in sorted_names:
        root = find(name)
        clusters_map.setdefault(root, [])
        if name != root:
            clusters_map[root].append(name)

    result = []
    for canonical, aliases in clusters_map.items():
        aliases_sorted = sorted(aliases, key=lambda n: len(n.split()), reverse=True)
        result.append({"canonical": canonical, "aliases": aliases_sorted})

    result.sort(key=lambda c: (-len(c["aliases"]), c["canonical"]))
    return result


def _clean_markdown_line(line: str) -> str:
    """
    Nettoie une ligne Markdown pour NER :
    - supprime les images ![alt](url)
    - remplace les liens [texte](url) par leur texte seul
    - supprime les balises HTML résiduelles
    - supprime les marqueurs Markdown (#, *, _, `, >)
    """
    # Images : supprimer complètement
    line = re.sub(r"!\[.*?\]\(.*?\)", "", line)
    # Liens Markdown : ne garder que le texte [texte](url) → texte
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    # Liens Markdown résiduels incomplets [texte]
    line = re.sub(r"\[([^\]]+)\]", r"\1", line)
    # HTML tags
    line = re.sub(r"<[^>]+>", " ", line)
    # Balises Markdown de structure (titres, listes, citations)
    line = re.sub(r"^#+\s+", "", line)
    line = re.sub(r"^[>*\-]\s+", "", line)
    # Gras/italique **text** / *text* / __text__ / _text_
    line = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", line)
    # Backticks inline `code`
    line = re.sub(r"`[^`]+`", "", line)
    # URLs résiduelles
    line = re.sub(r"https?://\S+", "", line)
    # Références numérotées résiduelles [1], [2], (#ref-1), etc.
    line = re.sub(r"\[#[^\]]+\]", "", line)
    line = re.sub(r"\(\#[^)]+\)", "", line)
    line = re.sub(r"\d+$", "", line)  # chiffres en fin de token collé (ex. "Decoppet2")
    # Chiffres de note de bas de page collés après un mot (ex. "Decoppet2")
    line = re.sub(r"(\w)\d+\b", r"\1", line)
    return line.strip()


def _is_valid_person_name(name: str) -> bool:
    """
    Filtre les faux positifs évidents :
    - moins de 2 caractères
    - contient des slash, underscore, point (chemins/URLs)
    - ressemble à un identifiant technique
    - contient des noms de lieux connus isolés
    - ressemble à un titre/section sans prénoms
    - est un mot générique isolé (sauf prénoms très courts comme "Jean", "Paul")
    """
    name = name.strip()
    if len(name) < 3:
        return False
    if re.search(r"[/_\\.]", name):
        return False
    if re.match(r"^\d+$", name):
        return False
    if name.lower() in _PERSON_STOPWORDS:
        return False
    # Noms plausibles : au moins une lettre majuscule
    if not re.search(r"[A-ZÀ-Ö]", name):
        return False
    
    # Exclure les noms qui sont simplement des lieux connus
    if name.lower() in _KNOWN_PLACES:
        return False
    
    # Exclure les noms tout en majuscules qui ressemblent à des titres/sections
    # (ex: "RESERVATION DE SALLE", mais pas "JOHN SMITH")
    if name.isupper() and len(name) > 15:
        return False
    
    # Exclure les articles + noms seuls sans contexte de personne
    # (ex: "la Présidente", "le Bureau")
    if re.match(r"^(la|le|les|un|une|des|un|une)\s+\w+$", name.lower()):
        return False
    
    # Exclure les mots qui débutent par un article/particule préposée
    # mais gardez les vrais noms nobles (von Wille, etc.)
    if len(name.split()) == 1 and re.match(r"^(la|le|les)$", name.lower()):
        return False
    
    # Exclure les mots trop courts qui font partie de libellés de documents
    # (ex: "Charge" isolé dans un diagramme)
    # mais garder les vrais prénoms courts (Jean, Paul, etc.)
    if len(name) <= 3 and not re.match(r"^(Jean|Paul|Marc|Luc|Anne|Marie|José|Nils|Tim|Tom|Max|Lea|Ima|Ana|Ella|etc)$", name, re.IGNORECASE):
        return False
    
    return True


_ROMAN_NUMERAL_RE = re.compile(r"^(?:[IVXLCDM]{1,6})$", re.IGNORECASE)

# Lieux connus à exclure de la NER (noms de communes, régions, etc.)
_KNOWN_PLACES = {
    "saint-george",
    "saint george",
    "nyon",
    "begnins",
    "burtigny",
    "coinsins",
    "duillier",
    "le vaud",
    "longirod",
    "marchissy",
    "tartegnin",
    "vich",
    "zurich",
    "bâle",
    "genève",
    "lausanne",
    "vaud",
    "jura",
    "esplanade",
    "pierre sanche",
    "clavalles",
    "vernes"
}

# Motifs institutionnels/titres à exclure
_INSTITUTIONAL_KEYWORDS = {
    "réservation de salle",
    "reservation de salle",
    "salle polyvalente",
    "commission",
    "assermentation",
    "conseil",
    "tribunal",
    "département",
    "bureau",
    "service",
    "caveau",
    "stand de tir",
    "cabane",
    "chalet",
    "administration",
    "gestion et finances",
    "gestion finances",
    "finances",
    "charge",
    "rémunération",
    "remuneration",
    "salaire"
}


def _is_institutional_false_positive(ent_text: str, line_text: str, raw_line: str = "") -> bool:
    """
    Détecte les faux positifs dus à des entités institutionnelles, sections ou lieux.

    Cas détectés :
    1. Noms de lieux connus (Saint-George, Nyon, etc.)
    2. Titres/sections (RESERVATION DE SALLE, Salle polyvalente, etc.)
    3. Noms composés avec des lieux (Saint-George Tél, Saint-George Généralités, etc.)
    4. Chiffres romains isolés (tribunal divisionnaire V)
    5. Noms génériques (Salle, Bureau, Caveau)
    6. Formules de salutation (la Présidente, Madame la Présidente, etc.)
    7. Mots isolés qui sont des libellés textes (Charge, etc.)
    """
    t = ent_text.strip().lower()
    l = line_text.strip().lower()
    r = raw_line.strip().lower()

    # 0. Exclure les mots très courts qui sont typiquement des libellés
    # (Charge, Stand, etc.) sauf s'ils sont des initiales d'une personne ("J.", "Y.", etc.)
    if len(t) <= 3 and not re.match(r"^[a-z]\.?$", t):
        # Vérifier si c'est dans un contexte institutionnel
        if any(keyword in l for keyword in ("charge", "maximum", "diagramme", "photo", "texte")):
            return True

    # 1. Exclure si la ligne est un titre/section en majuscules
    if raw_line and raw_line.isupper() and any(
        marker in r for marker in ("reservation", "salle", "commission", "conseil")
    ):
        return True

    # 2. Exclure si le nom contient un lieu connu
    if any(place in t for place in _KNOWN_PLACES):
        return True

    # 3. Exclure les noms génériques de bâtiments/salles
    generic_names = {"salle", "bureau", "caveau", "stand", "cabane", "chalet", "administration"}
    if t in generic_names:
        return True

    # 4. Exclure si c'est un motif institutionnel clé
    if any(keyword in t for keyword in _INSTITUTIONAL_KEYWORDS):
        return True

    # 5. Exclure les chiffres romains seuls dans un contexte institutionnel
    if _ROMAN_NUMERAL_RE.match(t.split()[0] if t.split() else "") and any(
        marker in l for marker in ("tribunal", "conseil", "commission", "divisionnaire")
    ):
        return True

    # 6. Exclure les noms débutant par un lieu + un titre ou un numéro
    # Ex: "Saint-George Tél", "Saint-George Généralités"
    for place in _KNOWN_PLACES:
        if t.startswith(place) and len(t) > len(place):
            remainder = t[len(place):].strip()
            # Si ce qui suit est un titre/mot-clé, c'est un faux positif
            if any(
                marker in remainder
                for marker in ("tél", "telephone", "généralité", "generalite", "plan", "adresse")
            ):
                return True

    # 7. Détection des formules de salutation ("la Présidente", "Madame la Présidente", etc.)
    # Ces formules sont typiquement adressées à quelqu'un et précédées d'articles
    salutation_patterns = [
        r"^la\s+(présidente|presidente)",      # "la Présidente"
        r"^le\s+(président|president)",        # "le Président"
        r"^madame\s+la\s+(présidente|presidente)",  # "Madame la Présidente"
        r"^monsieur\s+le\s+(président|president)",  # "Monsieur le Président"
    ]
    if any(re.match(p, t) for p in salutation_patterns):
        return True

    # 8. Exclure si c'est un article suivi d'un seul mot (formule générique)
    if re.match(r"^(la|le|les|un|une|des)\s+\w+$", t):
        # Vérifier que ce n'est pas un prénom français connu (par heuristique)
        # Les articles isolés + 1 mot dans un contexte formel sont rarement des personnes
        if len(ent_text.split()) == 2 and re.match(r"^(la|le|les|un|une|des)", t):
            return True

    return False


def parse_markdown_pages(md_content: str) -> dict:
    """
    Parse un Markdown structuré par pages (## Page X).
    Retourne {page_num: {"text": str, "lines": [str, ...], "lines_raw": [str, ...]}}
    Les lignes sont nettoyées pour NER (liens, images, balisage supprimés).
    """
    # Supprimer le front matter YAML
    md_content = re.sub(r"^---\n.*?\n---\n", "", md_content, flags=re.DOTALL)

    pages = {}
    current_page = 0
    current_lines = []
    current_lines_raw = []

    for line in md_content.split("\n"):
        match = re.match(r"^##\s+Page\s+(\d+)", line)
        if match:
            # Enregistre la page précédente
            if current_page > 0:
                pages[current_page] = {
                    "text": "\n".join(current_lines),
                    "lines": current_lines.copy(),
                    "lines_raw": current_lines_raw.copy(),
                }
            current_page = int(match.group(1))
            current_lines = []
            current_lines_raw = []
        else:
            cleaned = _clean_markdown_line(line)
            current_lines.append(cleaned)
            current_lines_raw.append(line)

    # Dernière page (ou page 0 si pas de marqueurs ## Page X)
    if current_lines:
        if current_page == 0:
            current_page = 1  # document sans pagination explicite
        pages[current_page] = {
            "text": "\n".join(current_lines),
            "lines": current_lines.copy(),
            "lines_raw": current_lines_raw.copy(),
        }

    return pages


def _normalize_person_name_for_list(ent_text: str, raw_line: str, clean_line: str) -> str:
    """
    Normalize list entries of the form '- Nom Prénom' into 'Prénom Nom'.
    Also strips title prefixes like 'Madame', 'Monsieur', 'Dr.', etc.
    
    Special cases:
    - Handles bullet lists with title prefixes.
    - Strips standalone "Mme" / "Mlle" that precedes a real name.
    - Removes formulas like "la Présidente", "Madame la Présidente".
    """
    person = (ent_text or "").strip()
    if not person:
        return person

    raw = (raw_line or "").lstrip()
    
    # Early filter: if the entity is just "Mme", "Mlle", "M.", etc., it's likely a marker
    # that needs to be combined with the next word (but spaCy already grouped them)
    if person.lower() in ("mme", "mlle", "m.", "mme.", "mlle.", "dr.", "prof."):
        return ""  # Empty string will be filtered later in _is_valid_person_name

    # Check if this is a bullet list item with a title prefix
    bullet_match = re.match(r"^-\s*(madame|mme\.?|monsieur|m\.?|mr\.?|dr\.?|prof\.?|général|colonel)\s+(.+?)(?:\s*\(|$)", 
                             raw, re.IGNORECASE)
    if bullet_match:
        # Extract full name from raw line (after title prefix)
        full_name = bullet_match.group(2).strip()
        # Remove any trailing punctuation or parenthetical notes
        full_name = re.sub(r"\s*[\(\[].*$", "", full_name).strip()
        # Remove stray suffixes like "(suppléant)"
        full_name = re.sub(r"\s*\(.*\)\s*$", "", full_name).strip()
        if full_name and len(full_name) > len(person):
            person = full_name

    # 1. Enlever les préfixes de titre au début
    # Patterns: "Madame Claudia" → "Claudia", "Monsieur X" → "X", "Dr. Y" → "Y", etc.
    person = re.sub(
        r"^(madame|mme\.?|monsieur|m\.?|mr\.?|dr\.?|prof\.?|général|colonel|capitaine|lieutenant|sergeant|von|de|van|du)\s+",
        "",
        person,
        flags=re.IGNORECASE,
    ).strip()

    # 2. Filtrer les formules de salutation (la Présidente, le Président, etc.)
    if re.match(r"^(la|le|les)\s+(président|presidente|monsieur|madame)$", person.lower()):
        return ""  # Empty string will be filtered later

    clean = (clean_line or "").strip()
    if not raw.startswith("-"):
        return person

    # Only apply when the entity is the whole cleaned bullet line (after title removal).
    if person != clean:
        return person

    tokens = person.split()
    if len(tokens) != 2:
        return person

    first, second = tokens[0], tokens[1]
    # Heuristic: bullet lists in these sources often use "Nom Prénom".
    return f"{second} {first}"


def extract_entities(
    md_path: str,
    lang: str = "fr",
    min_confidence: float = 0.0,
    insert_db: bool = False,
    *,
    quiet: bool = False,
    log_file: str | Path | None = None,
) -> dict:
    """
    Extrait les entités PERSON d'un fichier Markdown avec spaCy.

    Retourne {
        "file": path,
        "language": lang,
        "pages_total": int,
        "persons_count": int,
        "mentions": [
            {
                "person": str,
                "page": int,
                "line_start": int,
                "line_end": int,
                "confidence": float,
                "quote": str,
            },
            ...
        ]
    }
    """
    md_file = Path(md_path)
    if not md_file.exists():
        print(f"Erreur : fichier non trouvé : {md_path}", file=sys.stderr)
        sys.exit(1)

    _emit(f"[extract_entities] Chargement du fichier : {md_path}", quiet=quiet, log_file=log_file)
    md_content = md_file.read_text(encoding="utf-8")

    nlp = load_spacy_model(lang, quiet=quiet, log_file=log_file)

    _emit("[extract_entities] Parsing des pages...", quiet=quiet, log_file=log_file)
    pages = parse_markdown_pages(md_content)
    _emit(f"[extract_entities] {len(pages)} pages trouvées", quiet=quiet, log_file=log_file)

    mentions = []
    persons_seen = set()

    for page_num, page_data in sorted(pages.items()):
        page_lines = page_data["lines"]
        page_lines_raw = page_data.get("lines_raw", [""] * len(page_lines))

        # Traitement ligne par ligne pour éviter la fusion d'entités entre lignes adjacentes.
        for idx, line_text in enumerate(page_lines, start=1):
            if not line_text.strip():
                continue

            doc = nlp(line_text)
            raw_line = page_lines_raw[idx - 1] if 0 <= idx - 1 < len(page_lines_raw) else ""

            for ent in doc.ents:
                if ent.label_ != "PER":
                    continue

                person_name = _normalize_person_name_for_list(ent.text, raw_line, line_text)

                # Filtre les faux positifs évidents
                if not _is_valid_person_name(person_name):
                    continue

                # Score de confiance (spaCy ne donne pas toujours un score explicite)
                confidence = getattr(ent, "confidence", 0.95)
                if confidence < min_confidence:
                    continue

                if _is_institutional_false_positive(person_name, line_text, raw_line):
                    continue

                mention = {
                    "person": person_name,
                    "page": page_num,
                    "line_start": idx,
                    "line_end": idx,
                    "confidence": round(confidence, 3),
                    "quote": person_name,
                }
                mentions.append(mention)
                persons_seen.add(person_name)

    result = {
        "file": str(md_file),
        "language": lang,
        "pages_total": len(pages),
        "persons_unique": len(persons_seen),
        "mentions_count": len(mentions),
        "mentions": mentions,
        "clusters": cluster_names(list(persons_seen)),
    }

    return result


def _build_output_lines(result: dict, verbose: bool = False) -> list[str]:
    lines = [
        "" + "=" * 80,
        f"EXTRACTION spaCy: {result['file']}",
        f"Langue: {result['language']} | Pages: {result['pages_total']}",
        f"Personnes uniques: {result['persons_unique']} | Mentions: {result['mentions_count']}",
        "=" * 80,
    ]

    if not result["mentions"]:
        lines.append("✗ Aucune personne détectée")
        return lines

    sorted_mentions = sorted(result["mentions"], key=lambda m: (m["page"], m["line_start"]))

    current_page = None
    for mention in sorted_mentions:
        page = mention["page"]
        if page != current_page:
            lines.append(f"\n─ Page {page}")
            current_page = page

        confidence_pct = int(mention["confidence"] * 100)
        line_info = f"L{mention['line_start']}"
        if mention["line_end"] > mention["line_start"]:
            line_info += f"–{mention['line_end']}"

        person = mention["person"]
        confidence_bar = "█" * min(confidence_pct // 10, 10)
        lines.append(f"  {line_info:12} │ {person:35} │ {confidence_bar:12} {confidence_pct}%")
        if verbose and mention["quote"]:
            lines.append(f"               │ « {mention['quote'][:60]}... »")

    clusters = result.get("clusters", [])
    multi = [c for c in clusters if c["aliases"]]
    lines.append(f"\n{'─' * 80}")
    if multi:
        lines.append(f"CLUSTERS D'ALIASES ({len(multi)} groupe(s) détecté(s))")
        lines.append(f"{'─' * 80}")
        for c in multi:
            aliases_str = ", ".join(f'\"{a}\"' for a in c["aliases"])
            lines.append(f"  ► \"{c['canonical']}\"  ←  {aliases_str}")
    else:
        lines.append("  (Aucun alias détecté au sein de ce document)")
    lines.append("")
    return lines


def format_output(result: dict, verbose: bool = False) -> None:
    """Affiche les résultats de manière lisible."""
    for line in _build_output_lines(result, verbose=verbose):
        print(line)


def append_output_log(result: dict, log_file: str | Path | None, verbose: bool = False) -> None:
    """Écrit les résultats NER dans un fichier de log global."""
    if not log_file:
        return
    _append_to_log(log_file, "\n".join(_build_output_lines(result, verbose=verbose)))


def _resolve_source_name(markdown_file: str) -> str:
    """Résout le chemin source stocké en base (relatif à `sources/` si possible)."""
    md_path_obj = Path(markdown_file).resolve()
    parts = md_path_obj.parts
    idx = next((i for i, p in enumerate(parts) if p == "sources"), None)
    return str(Path(*parts[idx:]).as_posix()) if idx is not None else md_path_obj.name


def extract_entities_to_db(
    markdown_file: str,
    *,
    lang: str = "fr",
    min_confidence: float = 0.0,
    reanalyse: bool = False,
    quiet: bool = False,
    log_file: str | Path | None = None,
) -> dict:
    """API programmatique: extrait les entités puis insère les mentions en base.

    Cette fonction évite un sous-processus par document; le modèle spaCy reste donc
    en mémoire et le cache LRU de `load_spacy_model` est effectif sur les appels suivants.
    """
    source_name = _resolve_source_name(markdown_file)

    con = get_connection()
    try:
        if source_has_mentions(con, source_name) and not reanalyse:
            _emit(
                f"[insert] Source déjà traitée, extraction/insert ignorées : {source_name}. "
                f"Utilisez reanalyse=True pour forcer une nouvelle analyse.",
                quiet=quiet,
                log_file=log_file,
            )
            return {
                "action": "skipped",
                "source": source_name,
                "reason": "already_processed",
                "inserted": 0,
                "deleted_mentions": 0,
            }
    finally:
        con.close()

    result = extract_entities(
        markdown_file,
        lang=lang,
        min_confidence=min_confidence,
        insert_db=False,
        quiet=quiet,
        log_file=log_file,
    )

    con = get_connection()
    try:
        deleted_count = delete_mentions_for_source(con, source_name)
        if deleted_count > 0:
            _emit(
                f"[insert] {deleted_count} mentions existantes supprimées pour la source : {source_name}",
                quiet=quiet,
                log_file=log_file,
            )

        alias_to_canonical: dict[str, str] = {}
        alias_to_aliases: dict[str, list[str]] = {}
        for cluster in result["clusters"]:
            canonical = cluster["canonical"]
            all_forms = [canonical] + cluster["aliases"]
            for form in all_forms:
                alias_to_canonical[form] = canonical
                alias_to_aliases[canonical] = cluster["aliases"]

        inserted = 0
        skipped = 0
        for mention in result["mentions"]:
            try:
                raw_name = mention["person"]
                canonical_name = alias_to_canonical.get(raw_name, raw_name)
                person_key = re.sub(r"[^a-z0-9]+", "_", canonical_name.lower()).strip("_")
                aliases = alias_to_aliases.get(canonical_name, [])
                if raw_name != canonical_name and raw_name not in aliases:
                    aliases = list(aliases) + [raw_name]

                upsert_person(con, person_key, canonical_name, aliases=aliases)
                status = add_mention(
                    con,
                    person_key=person_key,
                    source=source_name,
                    page=mention["page"],
                    line_start=mention["line_start"],
                    line_end=mention["line_end"],
                    quote=mention["quote"],
                    extractor="spacy",
                    confidence=mention["confidence"],
                )
                if status["action"] == "created":
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:
                _emit(
                    f"  [insert][WARN] Erreur pour {mention['person']}: {exc}",
                    quiet=quiet,
                    log_file=log_file,
                )
    finally:
        con.close()

    append_output_log(result, log_file, verbose=False)
    _append_to_log(
        log_file,
        f"[insert] Résumé: inserted={inserted}, skipped={skipped}, deleted_mentions={deleted_count}",
    )

    return {
        "action": "inserted",
        "source": source_name,
        "inserted": inserted,
        "skipped": skipped,
        "deleted_mentions": deleted_count,
        "persons_unique": result["persons_unique"],
        "mentions_count": result["mentions_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrait les entités nommées (personnes) d'un fichier Markdown avec spaCy.",
    )
    parser.add_argument(
        "markdown_file",
        help="Chemin du fichier Markdown à analyser",
    )
    parser.add_argument(
        "--lang",
        choices=["fr", "de"],
        default="fr",
        help="Langue du modèle spaCy (défaut: fr)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="Score de confiance minimum à afficher (0.0–1.0, défaut: 0.0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Affiche aussi les extraits de texte (quotes)",
    )
    parser.add_argument(
        "--insert",
        action="store_true",
        help="Insère les mentions détectées dans la base de données SQLite",
    )
    parser.add_argument(
        "--reanalyse",
        action="store_true",
        help="Force une nouvelle analyse NER même si la source a déjà des mentions (à utiliser avec --insert)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Exporte le résultat en JSON (optionnel)",
    )

    args = parser.parse_args()

    source_name: str | None = None

    # Vérification en amont: si la source est déjà en base, on évite complètement la NER
    # sauf si l'utilisateur force une réanalyse.
    if args.insert:
        md_path_obj = Path(args.markdown_file).resolve()
        parts = md_path_obj.parts
        idx = next((i for i, p in enumerate(parts) if p == "sources"), None)
        source_name = str(Path(*parts[idx:]).as_posix()) if idx is not None else md_path_obj.name

        con = get_connection()
        try:
            if source_has_mentions(con, source_name) and not args.reanalyse:
                print(
                    f"[insert] Source déjà traitée, extraction/insert ignorées : {source_name}. "
                    f"Utilisez --reanalyse pour forcer une nouvelle analyse."
                )
                return
        finally:
            con.close()

    # Extraction
    result = extract_entities(
        args.markdown_file,
        lang=args.lang,
        min_confidence=args.min_confidence,
        insert_db=False,  # insérer après affichage
    )

    # Affichage
    format_output(result, verbose=args.verbose)

    # Insertion optionnelle dans la BD
    if args.insert:
        print("[insert] Insertion des mentions dans la BD...")
        if source_name is None:
            md_path_obj = Path(args.markdown_file).resolve()
            parts = md_path_obj.parts
            idx = next((i for i, p in enumerate(parts) if p == "sources"), None)
            source_name = str(Path(*parts[idx:]).as_posix()) if idx is not None else md_path_obj.name

        con = get_connection()
        try:
            # Supprime d'abord toutes les mentions existantes pour cette source
            deleted_count = delete_mentions_for_source(con, source_name)
            if deleted_count > 0:
                print(f"[insert] {deleted_count} mentions existantes supprimées pour la source : {source_name}")

            # Construit un mapping alias → nom canonique à partir des clusters
            alias_to_canonical: dict[str, str] = {}
            alias_to_aliases: dict[str, list[str]] = {}
            for cluster in result["clusters"]:
                canonical = cluster["canonical"]
                all_forms = [canonical] + cluster["aliases"]
                for form in all_forms:
                    alias_to_canonical[form] = canonical
                    alias_to_aliases[canonical] = cluster["aliases"]

            inserted = 0
            skipped = 0
            for mention in result["mentions"]:
                try:
                    raw_name = mention["person"]
                    canonical_name = alias_to_canonical.get(raw_name, raw_name)
                    person_key = re.sub(r"[^a-z0-9]+", "_", canonical_name.lower()).strip("_")
                    aliases = alias_to_aliases.get(canonical_name, [])
                    # Ajoute les variantes non-canoniques comme aliases
                    if raw_name != canonical_name and raw_name not in aliases:
                        aliases = list(aliases) + [raw_name]

                    # Upsert personne canonique
                    upsert_person(con, person_key, canonical_name, aliases=aliases)
                    # Ajout mention (idempotent)
                    status = add_mention(
                        con,
                        person_key=person_key,
                        source=source_name,
                        page=mention["page"],
                        line_start=mention["line_start"],
                        line_end=mention["line_end"],
                        quote=mention["quote"],
                        extractor="spacy",
                        confidence=mention["confidence"],
                    )
                    if status["action"] == "created":
                        inserted += 1
                        canonical_info = f" (via alias)" if raw_name != canonical_name else ""
                        print(f"  ✓ {canonical_name}{canonical_info} (p. {mention['page']}, L{mention['line_start']})")
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"  ✗ Erreur pour {mention['person']}: {e}", file=sys.stderr)
        finally:
            con.close()
        print(f"[insert] {inserted} insertions, {skipped} ignorées (doublons)")

    # Export JSON optionnel
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[export] Résultat sauvegardé : {args.output}")


if __name__ == "__main__":
    main()

