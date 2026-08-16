#!/usr/bin/env python3
"""Télécharge les courbes de consommation électrique de Romande Energie.

Authentification:
- username + password depuis `.env`
- SMS OTP saisi à l'exécution
- Bearer token final utilisé pour les appels suivants

Cache:
- un cache séparé par utilisateur est maintenu sous `.agents/.cache/romande-energie/<user_slug>/`
- chaque mois est stocké dans `<granularity>/YYYY-MM.csv`
- les mois déjà présents ne sont jamais retéléchargés
- un fichier mensuel vide est un marqueur de fin d'historique (plus de données disponibles)

Sortie:
- un CSV fusionné est écrit dans `sources/romande-energie/<user_slug>/`
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import getpass
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[4]
BASE_URL = "https://api.espace-client.romande-energie.ch"
DEFAULT_CACHE_ROOT = REPO_ROOT / ".agents" / ".cache" / "romande-energie"
DEFAULT_OUT_ROOT = REPO_ROOT / "sources" / "romande-energie"
MAX_CHUNK_DAYS = 90
MAX_BACKWARD_MONTHS = 600
DATE_FMT = "%Y-%m-%d"
OUTPUT_TIMESTAMP_FMT = "%d.%m.%Y %H:%M:%S"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) corpus-lens/romande-energie"

LOGGER = logging.getLogger("romande_energie")


@dataclass(frozen=True)
class DateChunk:
    start: dt.date
    end: dt.date


@dataclass
class AuthState:
    session: requests.Session
    username: str
    password: str
    access_token: str | None = None
    account_id: str | None = None
    token_cache_file: Path | None = None
    claims: dict[str, Any] = field(default_factory=dict)
    login_payload: dict[str, Any] = field(default_factory=dict)
    otp_payload: dict[str, Any] = field(default_factory=dict)


def configure_logging() -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def slugify(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "user"


def parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value.strip(), DATE_FMT).date()
    except Exception as exc:  # noqa: BLE001
        raise argparse.ArgumentTypeError(f"Date invalide: {value!r} (format attendu: YYYY-MM-DD)") from exc


def parse_any_datetime(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value.astimezone().replace(tzinfo=None) if value.tzinfo is not None else value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, (int, float)) and value > 1_000_000_000:
        try:
            return dt.datetime.fromtimestamp(value)
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    candidates = [text.replace("Z", "+00:00"), text]
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
    ]
    for candidate in candidates:
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo is not None else parsed
        except Exception:  # noqa: BLE001
            pass
        for fmt in formats:
            try:
                return dt.datetime.strptime(candidate, fmt)
            except Exception:  # noqa: BLE001
                continue
    return None


def parse_curve_timestamp(value: str) -> dt.datetime | None:
    return parse_any_datetime(value)


def format_timestamp_for_output(value: dt.datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone()
    return value.strftime(OUTPUT_TIMESTAMP_FMT)


def decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def has_account_claims(claims: dict[str, Any]) -> bool:
    return bool(
        str(claims.get("user_account_id") or "").strip()
        or str(claims.get("clean_user_account_id") or "").strip()
    )


def extract_account_id_from_claims(claims: dict[str, Any]) -> str:
    return (
        str(claims.get("user_account_id") or "").strip()
        or str(claims.get("clean_user_account_id") or "").strip()
        or ""
    )


def extract_account_id_candidates_from_claims(claims: dict[str, Any]) -> list[str]:
    candidates = [
        str(claims.get("clean_user_account_id") or "").strip(),
        str(claims.get("user_account_id") or "").strip(),
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return ordered


def load_cached_access_token(cache_file: Path | None) -> str | None:
    if cache_file is None or not cache_file.exists():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    token = payload.get("access_token")
    if not isinstance(token, str):
        return None
    token = token.strip()
    return token or None


def load_cached_account_id(cache_file: Path | None) -> str | None:
    if cache_file is None or not cache_file.exists():
        return None
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    account_id = payload.get("account_id")
    if account_id is None:
        return None
    value = str(account_id).strip()
    return value or None


def save_cached_access_token(cache_file: Path | None, token: str, account_id: str | None = None) -> None:
    if cache_file is None:
        return
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token,
        "account_id": account_id,
        "cached_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_cached_access_token(cache_file: Path | None) -> None:
    if cache_file is None or not cache_file.exists():
        return
    try:
        cache_file.unlink()
    except Exception:  # noqa: BLE001
        return


def load_settings() -> tuple[str, str]:
    env_path = REPO_ROOT / ".env"
    
    if not env_path.exists():
        raise SystemExit(
            f"Fichier .env manquant: {env_path}\n"
            "Créez un fichier .env avec les variables ROMANDE_ENERGIE_USERNAME et ROMANDE_ENERGIE_PASSWORD"
        )
    
    success = load_dotenv(env_path)
    if not success:
        raise SystemExit(
            f"Impossible de charger le fichier .env: {env_path}\n"
            "Vérifiez que le fichier est accessible et lisible"
        )
    
    username = (os.getenv("ROMANDE_ENERGIE_USERNAME") or os.getenv("ROMANDE_USERNAME") or "").strip()
    password = (os.getenv("ROMANDE_ENERGIE_PASSWORD") or os.getenv("ROMANDE_PASSWORD") or "").strip()
    
    if not username:
        raise SystemExit(
            "Variable d'environnement manquante: ROMANDE_ENERGIE_USERNAME\n"
            "Assurez-vous que cette variable est définie dans le fichier .env"
        )
    
    if not password:
        raise SystemExit(
            "Variable d'environnement manquante: ROMANDE_ENERGIE_PASSWORD\n"
            "Assurez-vous que cette variable est définie dans le fichier .env"
        )
    
    return username, password


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/csv, */*",
            "Content-Type": "application/json",
            "Origin": "https://espace-client.romande-energie.ch",
            "Referer": "https://espace-client.romande-energie.ch/",
        }
    )
    return session


def normalize_bearer_token(token: str | None) -> str | None:
    if not token:
        return None
    value = token.strip()
    if not value:
        return None
    # L'API attend "Authorization: Bearer <jwt>".
    if " " in value:
        return value
    return f"Bearer {value}"


def send_request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    bearer: str | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    headers = {}
    auth_header = normalize_bearer_token(bearer)
    if auth_header:
        headers["Authorization"] = auth_header
    LOGGER.info("HTTP %s %s params=%s json=%s auth=%s", method.upper(), path, params or {}, bool(json_body), "yes" if auth_header else "no")
    response = session.request(
        method=method,
        url=f"{BASE_URL}{path}",
        headers=headers,
        json=json_body,
        params=params,
        timeout=120,
    )
    LOGGER.info("HTTP %s %s -> %s", method.upper(), path, response.status_code)
    return response


def raise_for_status_with_context(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text[:500].strip()
        raise RuntimeError(f"HTTP {response.status_code} sur {response.url}: {body}") from exc


def extract_error_markers(payload: Any) -> set[str]:
    markers: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_l = str(key).strip().lower()
                if key_l in {"code", "description", "detail", "message", "error"} and isinstance(item, str):
                    markers.add(item.strip().lower())
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return markers


def is_expired_bearer_response(response: requests.Response) -> bool:
    if response.status_code not in (401, 403):
        return False

    try:
        payload = response.json()
    except ValueError:
        return True

    markers = extract_error_markers(payload)
    auth_hints = (
        "token",
        "jwt",
        "bearer",
        "expired",
        "expire",
        "not_authenticated",
        "not authenticated",
        "authentication credentials were not provided",
        "authentication failed",
        "token_not_valid",
        "invalid token",
    )
    return any(any(hint in marker for hint in auth_hints) for marker in markers)


def api_request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    bearer: str | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    response = send_request(
        session,
        method,
        path,
        bearer=bearer,
        json_body=json_body,
        params=params,
    )
    raise_for_status_with_context(response)
    return response


def extract_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"Réponse JSON invalide pour {response.url}") from exc


def login(session: requests.Session, username: str, password: str) -> tuple[str, dict[str, Any]]:
    response = api_request(
        session,
        "POST",
        "/v2/login/",
        json_body={"username": username, "password": password},
    )
    data = extract_json(response)
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Le login n'a pas renvoyé de access_token")
    return str(token), data if isinstance(data, dict) else {}


def send_otp(session: requests.Session, bearer: str) -> str:
    response = api_request(session, "POST", "/v2/login/send-otp/", bearer=bearer)
    data = extract_json(response)
    otp_id = data.get("otp_id") if isinstance(data, dict) else None
    if not otp_id:
        raise RuntimeError("Le serveur n'a pas renvoyé d'otp_id")
    return str(otp_id)


def validate_otp(session: requests.Session, bearer: str, otp_id: str, otp_code: str) -> tuple[str, dict[str, Any]]:
    response = api_request(
        session,
        "POST",
        "/v2/login/validate-otp/",
        bearer=bearer,
        json_body={"otp_id": otp_id, "otp_code": otp_code},
    )
    data = extract_json(response)
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError("La validation OTP n'a pas renvoyé de access_token")
    return str(token), data if isinstance(data, dict) else {}


def authenticate(auth: AuthState, *, force: bool = False) -> str:
    if auth.access_token and not force:
        return auth.access_token

    if not force and not auth.access_token:
        cached_token = load_cached_access_token(auth.token_cache_file)
        if cached_token:
            claims = decode_jwt_payload(cached_token)
            if has_account_claims(claims):
                auth.access_token = cached_token
                auth.claims = claims
                auth.account_id = load_cached_account_id(auth.token_cache_file) or extract_account_id_from_claims(claims) or None
                LOGGER.info("Access token réutilisé depuis le cache: %s", auth.token_cache_file)
                return cached_token
            LOGGER.warning("Access token en cache ignoré (claims incomplets): %s", auth.token_cache_file)

    pending_bearer, login_payload = login(auth.session, auth.username, auth.password)
    login_claims = decode_jwt_payload(pending_bearer)
    login_account_id = extract_account_id_from_claims(login_claims)
    if login_account_id:
        auth.account_id = login_account_id
    otp_id = send_otp(auth.session, pending_bearer)
    otp_code = prompt_otp_code()
    final_bearer, otp_payload = validate_otp(auth.session, pending_bearer, otp_id, otp_code)

    auth.access_token = final_bearer
    auth.login_payload = login_payload if isinstance(login_payload, dict) else {}
    auth.otp_payload = otp_payload if isinstance(otp_payload, dict) else {}
    final_claims = decode_jwt_payload(final_bearer)
    auth.claims = final_claims or login_claims
    auth.account_id = extract_account_id_from_claims(final_claims) or auth.account_id
    save_cached_access_token(auth.token_cache_file, final_bearer, auth.account_id)
    return final_bearer


def authorized_api_request(
    auth: AuthState,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    retry_on_expired_token: bool = True,
) -> requests.Response:
    bearer = authenticate(auth)
    response = send_request(
        auth.session,
        method,
        path,
        bearer=bearer,
        json_body=json_body,
        params=params,
    )
    if retry_on_expired_token and is_expired_bearer_response(response):
        auth.access_token = None
        clear_cached_access_token(auth.token_cache_file)
        bearer = authenticate(auth, force=True)
        response = send_request(
            auth.session,
            method,
            path,
            bearer=bearer,
            json_body=json_body,
            params=params,
        )
    raise_for_status_with_context(response)
    return response


def first_dict_item(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
        return {}
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "contracts_accounts", "contractsAccounts"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                item = first_dict_item(value[0])
                return item or (value[0] if isinstance(value[0], dict) else {})
        return payload
    return {}


def extract_identifier(payload: Any) -> str | None:
    item = first_dict_item(payload)
    for key in (
        "id",
        "contract_id",
        "contractId",
        "contracts_account_id",
        "contractsAccountId",
        "contract_account_id",
        "contractAccountId",
    ):
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def extract_account_id_from_accounts_payload(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("results", "data", "items", "accounts"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                return extract_identifier(value[0])
    if isinstance(payload, list) and payload:
        return extract_identifier(payload[0])
    return extract_identifier(payload)


def fetch_current_account_id(auth: AuthState) -> str:
    # accountId provient du token du POST /v2/login/ (claims JWT), puis est mis en cache.
    # Si GET /v2/accounts/{accountId}/ répond 401/404, on force un relogin puis on retente.
    last_errors: list[str] = []
    for attempt in range(2):
        candidates: list[str] = []
        if auth.account_id:
            candidates.append(str(auth.account_id).strip())
        cached_account_id = load_cached_account_id(auth.token_cache_file)
        if cached_account_id:
            candidates.append(cached_account_id)
        candidates.extend(extract_account_id_candidates_from_claims(auth.claims))

        seen: set[str] = set()
        candidates = [candidate for candidate in candidates if candidate and not (candidate in seen or seen.add(candidate))]
        if not candidates:
            raise RuntimeError("Impossible de résoudre account_id depuis le login (claims JWT) ou le cache")

        errors: list[str] = []
        must_relogin = False
        for account_id in candidates:
            try:
                authorized_api_request(auth, "GET", f"/v2/accounts/{account_id}/")
                auth.account_id = account_id
                if auth.access_token:
                    save_cached_access_token(auth.token_cache_file, auth.access_token, account_id)
                return account_id
            except RuntimeError as exc:
                message = str(exc)
                errors.append(f"{account_id}: {message}")
                lower_message = message.lower()
                is_accounts_lookup_error = "/v2/accounts/" in lower_message and (
                    "http 401" in lower_message or "http 404" in lower_message
                )
                if attempt == 0 and is_accounts_lookup_error:
                    must_relogin = True
                    LOGGER.warning(
                        "Echec GET /v2/accounts/{accountId}/ (401/404). Re-login forcé puis nouvelle tentative."
                    )
                    break

        last_errors = errors
        if must_relogin:
            authenticate(auth, force=True)
            continue
        break

    raise RuntimeError(
        "Impossible de valider account_id via GET /v2/accounts/{accountId}/. "
        f"Tentatives: {' | '.join(last_errors)}"
    )


DATE_KEY_HINTS = (
    "start_date",
    "valid_from",
    "from_date",
    "begin_date",
    "date_debut",
    "created_at",
    "created_on",
    "activation_date",
    "opened_at",
    "subscription_date",
)


def collect_candidate_dates(payload: Any) -> list[dt.date]:
    found: list[dt.date] = []

    def walk(value: Any, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_l = str(key).lower()
                if key_l in DATE_KEY_HINTS or any(hint in key_l for hint in DATE_KEY_HINTS):
                    parsed = parse_any_datetime(item)
                    if parsed:
                        found.append(parsed.date())
                walk(item, key_l)
        elif isinstance(value, list):
            for item in value:
                walk(item, parent_key)
        elif isinstance(value, str) and parent_key and any(hint in parent_key for hint in DATE_KEY_HINTS):
            parsed = parse_any_datetime(value)
            if parsed:
                found.append(parsed.date())

    walk(payload)
    return sorted(set(found))


def infer_contract_start_date(payloads: Iterable[Any], fallback: dt.date | None = None) -> tuple[dt.date, str]:
    all_dates: list[dt.date] = []
    for payload in payloads:
        all_dates.extend(collect_candidate_dates(payload))
    if all_dates:
        return min(all_dates), "contract_metadata"
    if fallback is None:
        fallback = dt.date(2000, 1, 1)
    return fallback, "fallback"


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def month_end(day: dt.date) -> dt.date:
    if day.month == 12:
        next_month = dt.date(day.year + 1, 1, 1)
    else:
        next_month = dt.date(day.year, day.month + 1, 1)
    return next_month - dt.timedelta(days=1)


def previous_month(day: dt.date) -> dt.date:
    return month_start(day) - dt.timedelta(days=1)


def iter_month_starts_backward(from_day: dt.date) -> Iterable[dt.date]:
    cursor = month_start(from_day)
    while True:
        yield cursor
        cursor = month_start(previous_month(cursor))


def month_chunk_path(cache_root: Path, granularity: str, month_first_day: dt.date) -> Path:
    granularity_dir = cache_root / granularity.upper()
    granularity_dir.mkdir(parents=True, exist_ok=True)
    return granularity_dir / f"{month_first_day.strftime('%Y-%m')}.csv"


def discover_cached_month_starts(cache_root: Path, granularity: str) -> list[dt.date]:
    granularity_dir = cache_root / granularity.upper()
    if not granularity_dir.exists():
        return []

    months: list[dt.date] = []
    for path in sorted(granularity_dir.glob("*.csv")):
        match = re.fullmatch(r"(\d{4})-(\d{2})", path.stem)
        if not match:
            continue
        try:
            months.append(dt.date(int(match.group(1)), int(match.group(2)), 1))
        except ValueError:
            continue
    return sorted(set(months))


def chunk_path(cache_root: Path, granularity: str, chunk: DateChunk) -> Path:
    granularity_dir = cache_root / granularity.upper()
    granularity_dir.mkdir(parents=True, exist_ok=True)
    return granularity_dir / f"{chunk.start.strftime(DATE_FMT)}__{chunk.end.strftime(DATE_FMT)}.csv"


def discover_cached_chunks(cache_root: Path, granularity: str) -> list[DateChunk]:
    granularity_dir = cache_root / granularity.upper()
    if not granularity_dir.exists():
        return []
    chunks: list[DateChunk] = []
    for path in sorted(granularity_dir.glob("*.csv")):
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})__(\d{4}-\d{2}-\d{2})", path.stem)
        if not match:
            continue
        try:
            chunks.append(DateChunk(parse_date(match.group(1)), parse_date(match.group(2))))
        except Exception:  # noqa: BLE001
            continue
    return sorted(chunks, key=lambda item: (item.start, item.end))


def merge_intervals(intervals: Iterable[DateChunk]) -> list[DateChunk]:
    ordered = sorted(intervals, key=lambda item: (item.start, item.end))
    if not ordered:
        return []
    merged: list[DateChunk] = [ordered[0]]
    one_day = dt.timedelta(days=1)
    for chunk in ordered[1:]:
        last = merged[-1]
        if chunk.start <= last.end + one_day:
            merged[-1] = DateChunk(last.start, max(last.end, chunk.end))
        else:
            merged.append(chunk)
    return merged


def daterange_chunks(start: dt.date, end: dt.date) -> list[DateChunk]:
    if start > end:
        return []
    chunks: list[DateChunk] = []
    cursor = start
    one_day = dt.timedelta(days=1)
    max_delta = dt.timedelta(days=MAX_CHUNK_DAYS)
    while cursor <= end:
        chunk_end = min(end, cursor + max_delta)
        chunks.append(DateChunk(cursor, chunk_end))
        cursor = chunk_end + one_day
    return chunks


def uncovered_chunks(start: dt.date, end: dt.date, covered: Iterable[DateChunk]) -> list[DateChunk]:
    if start > end:
        return []
    one_day = dt.timedelta(days=1)
    merged = merge_intervals(covered)
    gaps: list[DateChunk] = []
    cursor = start
    for interval in merged:
        if interval.end < cursor:
            continue
        if interval.start > end:
            break
        if cursor < interval.start:
            gaps.append(DateChunk(cursor, min(end, interval.start - one_day)))
        cursor = max(cursor, interval.end + one_day)
        if cursor > end:
            break
    if cursor <= end:
        gaps.append(DateChunk(cursor, end))
    return [gap for gap in gaps if gap.start <= gap.end]


def normalize_csv_text(csv_text: str) -> str:
    # Harmonise les fins de ligne et supprime les lignes vides de transport.
    text = csv_text.replace("\ufeff", "")
    lines = [line.strip("\r") for line in text.splitlines() if line.strip()]
    return "\n".join(lines) + ("\n" if lines else "")


def is_empty_month_marker(csv_text: str) -> bool:
    # Marqueur d'arrêt du backfill: fichier mensuel explicitement vide.
    return normalize_csv_text(csv_text) == ""


def is_cached_month_complete(csv_text: str, month_first_day: dt.date, requested_end: dt.date) -> bool:
    # Heuristique: un mois est complet si ses donnees couvrent du debut du mois
    # jusqu'a la fin du mois (ou jusqu'a requested_end pour le mois courant).
    _, month_rows = read_curve_rows(csv_text)
    if not month_rows:
        return False

    dates = [timestamp.date() for timestamp, _row in month_rows]
    min_date = min(dates)
    max_date = max(dates)
    expected_end = min(month_end(month_first_day), requested_end)
    return min_date <= month_first_day and max_date >= expected_end


def download_curve_chunk(auth: AuthState, contract_id: str, granularity: str, chunk: DateChunk, output_path: Path) -> str:
    response = authorized_api_request(
        auth,
        "GET",
        f"/v2/contracts-accounts/{contract_id}/curves/download/",
        params={
            "granularity": granularity,
            "start_date": chunk.start.strftime(DATE_FMT),
            "end_date": chunk.end.strftime(DATE_FMT),
        },
    )
    content_type = response.headers.get("content-type", "").lower()
    if "json" in content_type:
        data = extract_json(response)
        raise RuntimeError(f"Réponse JSON inattendue pour la courbe: {json.dumps(data, ensure_ascii=False)}")

    text = normalize_csv_text(response.text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return text


def read_curve_rows(csv_text: str) -> tuple[list[str], list[tuple[dt.datetime, list[str]]]]:
    lines = normalize_csv_text(csv_text).splitlines()
    reader = csv.reader(lines, delimiter=";")
    rows = list(reader)
    if not rows:
        return [], []

    header = rows[0]
    data: list[tuple[dt.datetime, list[str]]] = []
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        parsed = parse_curve_timestamp(row[0].strip())
        if parsed is None:
            continue
        data.append((parsed, row))
    return header, data


def merge_curve_chunks(
    chunk_paths: list[Path],
    requested_start: dt.date,
    requested_end: dt.date,
) -> tuple[list[str], list[tuple[dt.datetime, list[str]]]]:
    merged_header: list[str] = []
    collected: list[tuple[dt.datetime, list[str]]] = []
    seen: set[str] = set()
    start_dt = dt.datetime.combine(requested_start, dt.time.min)
    end_dt = dt.datetime.combine(requested_end, dt.time.max)

    for path in sorted(chunk_paths, key=str):
        header, rows = read_curve_rows(path.read_text(encoding="utf-8"))
        if header and not merged_header:
            merged_header = header
        for timestamp, row in rows:
            if timestamp < start_dt or timestamp > end_dt:
                continue
            key = timestamp.astimezone(dt.timezone.utc).isoformat() if timestamp.tzinfo else timestamp.isoformat(sep=" ", timespec="seconds")
            if key in seen:
                continue
            seen.add(key)
            collected.append((timestamp, row))

    collected.sort(key=lambda item: item[0])
    return merged_header, collected


def write_merged_csv(path: Path, header: list[str], rows: list[tuple[dt.datetime, list[str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        if header:
            writer.writerow(header)
        for timestamp, row in rows:
            output_row = list(row)
            if output_row:
                output_row[0] = format_timestamp_for_output(timestamp)
            writer.writerow(output_row)


def prompt_otp_code() -> str:
    code = getpass.getpass("Code SMS OTP: ").strip()
    if not code:
        raise SystemExit("Code OTP vide")
    return code


def resolve_account_and_contract(auth: AuthState, account_id: str) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    # Les IDs de compte peuvent changer après un re-login OTP. On retente une fois
    # avec l'ID rafraîchi depuis les claims JWT si l'ancien répond 404.
    current_account_id = account_id
    tried_account_ids: set[str] = set()

    for _attempt in range(2):
        tried_account_ids.add(current_account_id)
        try:
            account_payload = extract_json(authorized_api_request(auth, "GET", f"/v2/accounts/{current_account_id}/"))
            contracts_accounts_payload = extract_json(
                authorized_api_request(auth, "GET", f"/v2/accounts/{current_account_id}/contracts-accounts/")
            )

            contract_id = extract_identifier(contracts_accounts_payload)
            if not contract_id:
                contract_id = extract_identifier(account_payload)
            if not contract_id:
                contract_id = str(current_account_id)

            return (
                account_payload if isinstance(account_payload, dict) else {},
                contracts_accounts_payload if isinstance(contracts_accounts_payload, dict) else {},
                contract_id,
                current_account_id,
            )
        except RuntimeError as exc:
            message = str(exc)
            lower_message = message.lower()
            not_found_on_account = "http 404" in lower_message and f"/v2/accounts/{current_account_id}/" in lower_message
            refreshed_account_id = ""
            if not_found_on_account:
                try:
                    authenticate(auth, force=True)
                    refreshed_account_id = fetch_current_account_id(auth)
                except Exception as fetch_exc:  # noqa: BLE001
                    LOGGER.warning("Impossible de récupérer un account_id rafraîchi via les claims JWT: %s", fetch_exc)
                    refreshed_account_id = extract_account_id_from_claims(auth.claims)

            if not_found_on_account and refreshed_account_id and refreshed_account_id not in tried_account_ids:
                LOGGER.warning(
                    "account_id %s invalide apres authentification; nouvelle tentative avec %s",
                    current_account_id,
                    refreshed_account_id,
                )
                current_account_id = refreshed_account_id
                continue
            raise

    raise RuntimeError("Impossible de resoudre le compte et le contrat apres rafraichissement des identifiants")


def build_output_paths(out_root: Path, cache_root: Path, username: str, granularity: str) -> tuple[Path, Path]:
    user_slug = slugify(username)
    cache_user_root = cache_root / user_slug
    output_user_root = out_root / user_slug
    cache_user_root.mkdir(parents=True, exist_ok=True)
    output_user_root.mkdir(parents=True, exist_ok=True)
    return cache_user_root, output_user_root / f"romande_energie_{granularity.lower()}.csv"


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(
        description=(
            "Télécharge toutes les courbes de consommation Romande Energie avec cache par utilisateur "
            "(1 requête HTTP = 1 mois)."
        )
    )
    parser.add_argument(
        "--granularity",
        choices=("HOURLY", "QUARTER_HOURLY", "DAILY", "MONTHLY"),
        default="QUARTER_HOURLY",
        help="Granularité de la courbe",
    )
    parser.add_argument(
        "--max-months",
        type=int,
        default=MAX_BACKWARD_MONTHS,
        help="Nombre maximum de mois à parcourir vers le passé (sécurité)",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_ROOT, help="Dossier de sortie des CSV fusionnés")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_ROOT, help="Racine du cache local")
    args = parser.parse_args()

    username, password = load_settings()
    token_cache_file = args.cache_dir / slugify(username) / "access_token.json"
    auth = AuthState(
        session=build_session(),
        username=username,
        password=password,
        token_cache_file=token_cache_file,
    )

    authenticate(auth)
    claims = auth.claims
    account_id = fetch_current_account_id(auth)
    if not account_id:
        raise SystemExit("Impossible d'identifier le compte courant depuis /v2/accounts/")

    account_payload, contracts_accounts_payload, contract_id, account_id = resolve_account_and_contract(auth, account_id)
    inferred_start, start_source = infer_contract_start_date(
        [auth.login_payload, auth.otp_payload, claims, account_payload, contracts_accounts_payload]
    )
    requested_end = dt.date.today()

    cache_user_root, output_file = build_output_paths(args.out_dir, args.cache_dir, username, args.granularity)
    cache_granularity_dir = cache_user_root / args.granularity.upper()
    cache_granularity_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    reused: list[Path] = []
    data_chunk_paths: list[Path] = []
    data_month_starts: list[dt.date] = []
    first_empty_month: str | None = None
    refresh_month: dt.date | None = None

    cached_months = discover_cached_month_starts(cache_user_root, args.granularity)
    if cached_months:
        latest_cached_month = max(cached_months)
        latest_cached_path = month_chunk_path(cache_user_root, args.granularity, latest_cached_month)
        latest_cached_text = latest_cached_path.read_text(encoding="utf-8")

        if not is_empty_month_marker(latest_cached_text) and not is_cached_month_complete(
            latest_cached_text, latest_cached_month, requested_end
        ):
            refresh_month = latest_cached_month
            LOGGER.info(
                "Dernier mois en cache %s incomplet, il sera retéléchargé.",
                latest_cached_month.strftime("%Y-%m"),
            )

    for index, month_first_day in enumerate(iter_month_starts_backward(requested_end), start=1):
        if index > max(1, args.max_months):
            LOGGER.warning("Arrêt après %s mois inspectés (limite --max-months)", args.max_months)
            break

        month_last_day = month_end(month_first_day)
        chunk = DateChunk(
            start=month_first_day,
            end=min(month_last_day, requested_end),
        )
        target_path = month_chunk_path(cache_user_root, args.granularity, month_first_day)

        force_refresh = refresh_month is not None and month_first_day == refresh_month

        if target_path.exists() and not force_refresh:
            reused.append(target_path)
            csv_text = target_path.read_text(encoding="utf-8")
        else:
            csv_text = download_curve_chunk(auth, contract_id, args.granularity, chunk, target_path)
            downloaded.append(target_path)

        if is_empty_month_marker(csv_text):
            first_empty_month = month_first_day.strftime("%Y-%m")
            LOGGER.info("Fichier vide detecte pour %s, arrêt du backfill.", first_empty_month)
            break

        _, month_rows = read_curve_rows(csv_text)
        if not month_rows:
            # Compatibilite cache historique: transforme un mois sans lignes utiles
            # (ex: header seul) en marqueur vide pour garantir l'idempotence.
            target_path.write_text("", encoding="utf-8")
            first_empty_month = month_first_day.strftime("%Y-%m")
            LOGGER.info("Aucune donnée utile pour %s, marqueur vide ecrit puis arrêt du backfill.", first_empty_month)
            break

        data_month_starts.append(month_first_day)
        data_chunk_paths.append(target_path)

    if data_month_starts:
        requested_start = min(data_month_starts)
    else:
        requested_start = requested_end

    header, rows = merge_curve_chunks(data_chunk_paths, requested_start, requested_end)
    write_merged_csv(output_file, header, rows)

    summary = {
        "username": username,
        "user_slug": slugify(username),
        "account_id": account_id,
        "contract_id": contract_id,
        "granularity": args.granularity,
        "requested_start_date": requested_start.strftime(DATE_FMT),
        "requested_end_date": requested_end.strftime(DATE_FMT),
        "inferred_start_date": inferred_start.strftime(DATE_FMT),
        "inferred_start_source": start_source,
        "first_empty_month": first_empty_month,
        "cache_dir": str(cache_user_root),
        "output": str(output_file),
        "chunks_downloaded": len(downloaded),
        "chunks_reused": len(reused),
        "rows": len(rows),
        "months_with_data": len(data_chunk_paths),
        "cache_chunks": len(list(cache_granularity_dir.glob("*.csv"))),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

