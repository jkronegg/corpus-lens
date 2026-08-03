from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import hunspell as pyhunspell  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pyhunspell = None

try:
    from spylls.hunspell import Dictionary as SpyllsDictionary
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    SpyllsDictionary = None


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DICT_CACHE = ROOT / ".cache" / "hunspell"
WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+)*(?:-[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]+)*")
ROMAN_RE = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
MIXED_ALNUM_RE = re.compile(r"(?=.*[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ])(?=.*\d)")
BAD_CHAR_RE = re.compile(r"[�□■]")
SUSPICIOUS_CASE_RE = re.compile(r"[a-zà-ÿ][A-ZÀ-Ý][a-zà-ÿ]{2,}|[A-ZÀ-Ý]{2,}[a-zà-ÿ]{2,}[A-ZÀ-Ý]")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")
FRENCH_CLITICS = {"c", "d", "j", "l", "m", "n", "qu", "s", "t"}
DOWNLOADABLE_DICTIONARIES = {
    "fr": {
        "base_name": "fr",
        "aff_url": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr.aff",
        "dic_url": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr.dic",
    },
    "fr_fr": {
        "base_name": "fr",
        "aff_url": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr.aff",
        "dic_url": "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr.dic",
    },
}


@dataclass(slots=True)
class OcrQualityReport:
    input_path: str
    dictionary_aff: str
    dictionary_dic: str
    backend: str
    token_count: int
    checked_words: int
    valid_words: int
    invalid_words: int
    spell_ratio: float
    suspicious_token_ratio: float
    noisy_line_ratio: float
    bad_character_ratio: float
    quality_score: float
    quality_label: str
    top_unknown_words: list[list[object]]


class SpellCheckerProtocol:
    backend_name = "unknown"

    def check(self, word: str) -> bool:  # pragma: no cover - interface method
        raise NotImplementedError


class HunspellBindingChecker(SpellCheckerProtocol):
    backend_name = "hunspell"

    def __init__(self, aff_path: Path, dic_path: Path) -> None:
        if pyhunspell is None:
            raise RuntimeError("Le module Python 'hunspell' n'est pas disponible.")
        self._dict = pyhunspell.HunSpell(str(dic_path), str(aff_path))

    def check(self, word: str) -> bool:
        return bool(self._dict.spell(word))


class SpyllsChecker(SpellCheckerProtocol):
    backend_name = "spylls"

    def __init__(self, base_path: Path) -> None:
        if SpyllsDictionary is None:
            raise RuntimeError("Le module Python 'spylls' n'est pas disponible.")
        self._dict = SpyllsDictionary.from_files(str(base_path))

    def check(self, word: str) -> bool:
        return bool(self._dict.lookup(word))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _canonical_lang_key(lang: str) -> str:
    return (lang or "fr").strip().lower().replace("-", "_")


def _dictionary_candidates(lang: str) -> list[str]:
    key = _canonical_lang_key(lang)
    parts = [part for part in key.split("_") if part]
    candidates: list[str] = []

    if key:
        candidates.append(key)
    if len(parts) >= 2:
        candidates.append(f"{parts[0]}_{parts[1].upper()}")
        candidates.append(f"{parts[0]}-{parts[1].upper()}")
        candidates.append(f"{parts[0]}{parts[1].upper()}")
    if parts:
        candidates.append(parts[0])

    if parts and parts[0] == "fr":
        candidates.extend(["fr", "fr_FR", "fr-FR"])

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _strip_front_matter(markdown: str) -> str:
    if markdown.startswith("---"):
        parts = markdown.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\r\n")
    return markdown


def _markdown_to_text(markdown: str) -> str:
    text = _strip_front_matter(markdown)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^Pages détectées:\s*.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+Page\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\[header]:\s*#\s*\((.*?)\)\s*$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"^\[footer]:\s*#\s*\((.*?)\)\s*$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^]]*)]\([^)]*\)", r" \1 ", text)
    text = re.sub(r"\[([^]]+)]\([^)]*\)", r" \1 ", text)

    cleaned_lines: list[str] = []
    for line in text.split("\n"):
        if TABLE_SEPARATOR_RE.match(line):
            continue
        normalized = line.replace("|", " ")
        normalized = re.sub(r"^\s{0,3}#{1,6}\s+", "", normalized)
        cleaned_lines.append(normalized)

    text = "\n".join(cleaned_lines)
    text = text.replace("<br>", " ")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _iter_candidate_words(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def _normalize_word(word: str) -> str:
    return (word or "").replace("’", "'").strip("-'")


def _is_skippable_token(word: str) -> bool:
    if len(word) <= 1:
        return True
    if ROMAN_RE.fullmatch(word):
        return True
    if word.isupper() and len(word) <= 6:
        return True
    return False


def _is_suspicious_token(word: str) -> bool:
    if not word:
        return True
    if MIXED_ALNUM_RE.search(word):
        return True
    if SUSPICIOUS_CASE_RE.search(word):
        return True
    if re.search(r"['’]{2,}", word):
        return True
    if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]{8,}\d{2,}|\d{2,}[A-Za-zÀ-ÖØ-öø-ÿŒœÆæ]{8,}", word):
        return True
    return False


def _check_word(checker: SpellCheckerProtocol, word: str) -> bool:
    normalized = _normalize_word(word)
    if not normalized:
        return False

    direct_candidates = [normalized, normalized.lower(), normalized.capitalize()]
    for candidate in direct_candidates:
        if candidate and checker.check(candidate):
            return True

    if "'" in normalized:
        parts = [part for part in normalized.split("'") if part]
        if parts and all(part.lower() in FRENCH_CLITICS or _check_word(checker, part) for part in parts):
            return True

    if "-" in normalized:
        parts = [part for part in normalized.split("-") if part]
        if len(parts) >= 2 and all(_check_word(checker, part) for part in parts):
            return True

    return False


def _quality_label(score: float) -> str:
    if score >= 0.90:
        return "excellente"
    if score >= 0.80:
        return "bonne"
    if score >= 0.65:
        return "moyenne"
    if score >= 0.45:
        return "faible"
    return "très faible"


def analyze_text(text: str, checker: SpellCheckerProtocol, *, input_path: str = "", aff_path: Path | None = None, dic_path: Path | None = None) -> OcrQualityReport:
    plain_text = _markdown_to_text(text)
    tokens = _iter_candidate_words(plain_text)
    checked_words = 0
    valid_words = 0
    suspicious_tokens = 0
    invalid_counter: Counter[str] = Counter()

    for token in tokens:
        normalized = _normalize_word(token)
        if _is_skippable_token(normalized):
            continue
        checked_words += 1
        if _is_suspicious_token(normalized):
            suspicious_tokens += 1
        if _check_word(checker, normalized):
            valid_words += 1
        else:
            invalid_counter[normalized.lower()] += 1

    invalid_words = max(0, checked_words - valid_words)
    spell_ratio = valid_words / checked_words if checked_words else 0.0
    suspicious_ratio = suspicious_tokens / checked_words if checked_words else 1.0

    lines = [line.strip() for line in plain_text.splitlines() if line.strip()]
    noisy_lines = 0
    for line in lines:
        letters = sum(1 for char in line if char.isalpha())
        digits = sum(1 for char in line if char.isdigit())
        length = len(line)
        if length >= 20 and letters > 0:
            non_letters = length - letters
            if (non_letters / length) > 0.45 and digits < letters:
                noisy_lines += 1
    noisy_line_ratio = noisy_lines / len(lines) if lines else 0.0

    bad_character_ratio = len(BAD_CHAR_RE.findall(plain_text)) / max(1, len(plain_text))
    bad_character_penalty = clamp(bad_character_ratio * 12.0)

    quality_score = clamp(
        spell_ratio * 0.78
        + (1.0 - suspicious_ratio) * 0.14
        + (1.0 - noisy_line_ratio) * 0.05
        + (1.0 - bad_character_penalty) * 0.03
    )

    return OcrQualityReport(
        input_path=input_path,
        dictionary_aff=str(aff_path or ""),
        dictionary_dic=str(dic_path or ""),
        backend=checker.backend_name,
        token_count=len(tokens),
        checked_words=checked_words,
        valid_words=valid_words,
        invalid_words=invalid_words,
        spell_ratio=round(spell_ratio, 4),
        suspicious_token_ratio=round(suspicious_ratio, 4),
        noisy_line_ratio=round(noisy_line_ratio, 4),
        bad_character_ratio=round(bad_character_ratio, 6),
        quality_score=round(quality_score, 4),
        quality_label=_quality_label(quality_score),
        top_unknown_words=[[word, count] for word, count in invalid_counter.most_common(20)],
    )


def analyze_markdown_file(markdown_path: Path, checker: SpellCheckerProtocol, *, aff_path: Path | None = None, dic_path: Path | None = None) -> OcrQualityReport:
    content = Path(markdown_path).read_text(encoding="utf-8")
    return analyze_text(content, checker, input_path=str(Path(markdown_path).resolve()), aff_path=aff_path, dic_path=dic_path)


def _candidate_dictionary_dirs(explicit_dir: Path | None = None) -> list[Path]:
    dirs: list[Path] = []
    if explicit_dir is not None:
        dirs.append(explicit_dir)

    dirs.extend(
        [
            DEFAULT_DICT_CACHE,
            DEFAULT_DICT_CACHE / "fr",
            Path("C:/Program Files/Hunspell"),
            Path("C:/Program Files (x86)/Hunspell"),
            Path("C:/msys64/usr/share/hunspell"),
            Path("C:/msys64/mingw64/share/hunspell"),
            Path.home() / "AppData/Local/Programs/Hunspell",
        ]
    )

    seen: set[Path] = set()
    ordered: list[Path] = []
    for directory in dirs:
        resolved = directory.resolve() if directory.is_absolute() else (ROOT / directory).resolve()
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def _find_dictionary_pair(lang: str, dict_dir: Path | None = None) -> tuple[Path, Path] | None:
    candidates = _dictionary_candidates(lang)
    for base_dir in _candidate_dictionary_dirs(dict_dir):
        if not base_dir.exists():
            continue
        for candidate in candidates:
            aff_path = base_dir / f"{candidate}.aff"
            dic_path = base_dir / f"{candidate}.dic"
            if aff_path.exists() and dic_path.exists():
                return aff_path, dic_path
    return None


def _download_dictionary(lang: str, target_dir: Path) -> tuple[Path, Path]:
    key = _canonical_lang_key(lang)
    payload = DOWNLOADABLE_DICTIONARIES.get(key)
    if payload is None and key.startswith("fr"):
        payload = DOWNLOADABLE_DICTIONARIES["fr"]
    if payload is None:
        raise RuntimeError(f"Aucun téléchargement automatique n'est configuré pour la langue '{lang}'.")

    target_dir.mkdir(parents=True, exist_ok=True)
    base_name = payload["base_name"]
    aff_path = target_dir / f"{base_name}.aff"
    dic_path = target_dir / f"{base_name}.dic"

    for url_key, destination in (("aff_url", aff_path), ("dic_url", dic_path)):
        if destination.exists() and destination.stat().st_size > 0:
            continue
        with urllib.request.urlopen(payload[url_key]) as response:
            destination.write_bytes(response.read())

    return aff_path, dic_path


def load_spellchecker(
    *,
    lang: str = "fr",
    dict_dir: Path | None = None,
    aff_path: Path | None = None,
    dic_path: Path | None = None,
    download_if_missing: bool = False,
) -> tuple[SpellCheckerProtocol, Path, Path]:
    if bool(aff_path) ^ bool(dic_path):
        raise ValueError("Les options --aff et --dic doivent être fournies ensemble.")

    if aff_path is not None and dic_path is not None:
        resolved_aff = Path(aff_path).resolve()
        resolved_dic = Path(dic_path).resolve()
        if not resolved_aff.exists() or not resolved_dic.exists():
            raise FileNotFoundError("Les chemins --aff/--dic fournis n'existent pas.")
    else:
        pair = _find_dictionary_pair(lang, dict_dir)
        if pair is None and download_if_missing:
            download_target = (dict_dir or (DEFAULT_DICT_CACHE / _canonical_lang_key(lang))).resolve()
            pair = _download_dictionary(lang, download_target)
        if pair is None:
            searched = "\n- ".join(str(path) for path in _candidate_dictionary_dirs(dict_dir))
            raise FileNotFoundError(
                "Aucun dictionnaire Hunspell trouvé.\n"
                f"Langue demandée: {lang}\n"
                f"Répertoires testés:\n- {searched}\n"
                "Ajoutez --dict-dir, ou utilisez --download-dict pour récupérer un dictionnaire français LibreOffice."
            )
        resolved_aff, resolved_dic = (Path(pair[0]).resolve(), Path(pair[1]).resolve())

    if pyhunspell is not None:
        try:
            return HunspellBindingChecker(resolved_aff, resolved_dic), resolved_aff, resolved_dic
        except Exception:
            pass

    if SpyllsDictionary is not None:
        base_path = resolved_aff.with_suffix("")
        return SpyllsChecker(base_path), resolved_aff, resolved_dic

    raise RuntimeError(
        "Impossible de charger Hunspell: ni le module 'hunspell' ni 'spylls' n'est disponible. "
        "Installez par exemple: python -m pip install spylls"
    )


def _print_human_report(report: OcrQualityReport) -> None:
    print(f"Fichier               : {report.input_path}")
    print(f"Backend Hunspell      : {report.backend}")
    print(f"Dictionnaire (.aff)   : {report.dictionary_aff}")
    print(f"Dictionnaire (.dic)   : {report.dictionary_dic}")
    print(f"Tokens détectés       : {report.token_count}")
    print(f"Mots évalués          : {report.checked_words}")
    print(f"Mots valides          : {report.valid_words}")
    print(f"Mots invalides        : {report.invalid_words}")
    print(f"Ratio orthographique  : {report.spell_ratio:.4f}")
    print(f"Ratio tokens suspects : {report.suspicious_token_ratio:.4f}")
    print(f"Ratio lignes bruyantes: {report.noisy_line_ratio:.4f}")
    print(f"Ratio caractères KO   : {report.bad_character_ratio:.6f}")
    print(f"Score OCR estimé      : {report.quality_score:.4f} ({report.quality_label})")
    if report.top_unknown_words:
        print("Mots inconnus fréquents:")
        for word, count in report.top_unknown_words:
            print(f"  - {word}: {count}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estime la qualité d'un texte OCR à partir d'un dictionnaire Hunspell et d'un fichier Markdown."
    )
    parser.add_argument("input", type=Path, help="Chemin du fichier Markdown à analyser.")
    parser.add_argument("--lang", default="fr", help="Code langue Hunspell à chercher (défaut: fr).")
    parser.add_argument("--dict-dir", type=Path, help="Répertoire contenant les fichiers .aff/.dic.")
    parser.add_argument("--aff", type=Path, help="Chemin explicite du fichier .aff.")
    parser.add_argument("--dic", type=Path, help="Chemin explicite du fichier .dic.")
    parser.add_argument(
        "--download-dict",
        action="store_true",
        help="Télécharge automatiquement un dictionnaire français LibreOffice si aucun dictionnaire local n'est trouvé.",
    )
    parser.add_argument("--json", action="store_true", help="Affiche le rapport en JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        parser.error(f"Fichier introuvable: {input_path}")

    checker, aff_path, dic_path = load_spellchecker(
        lang=args.lang,
        dict_dir=args.dict_dir,
        aff_path=args.aff,
        dic_path=args.dic,
        download_if_missing=args.download_dict,
    )
    report = analyze_markdown_file(input_path, checker, aff_path=aff_path, dic_path=dic_path)

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    else:
        _print_human_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


