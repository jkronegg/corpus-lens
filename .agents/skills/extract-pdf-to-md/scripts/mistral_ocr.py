#!/usr/bin/env python3
"""OCR Mistral AI (API HTTP).

Usage:
    set MISTRAL_API_KEY=...
    python mistral_ocr.py --file "C:\\path\\document.pdf"
    python mistral_ocr.py --document-url "https://example.org/doc.pdf"
    python mistral_ocr.py --file "C:\\path\\document.pdf" --no-extract-images
    python mistral_ocr.py --extract-images-only --file "C:\\path\\document.pdf"
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import posixpath
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

API_BASE = "https://api.mistral.ai/v1"

# Charge les variables d'environnement depuis .env (si présent) sans écraser
# les variables déjà définies dans l'environnement système.
load_dotenv(override=False)


def _missing_api_key_help_message() -> str:
    help_file_uri = (Path(__file__).resolve().parent.parent / "mistral-ocr.md").as_uri()
    return (
        "Pas de cle d'API Mistral AI trouvée pour l'OCR.\n"
        "Ajoutez MISTRAL_API_KEY via --api-key, une variable d'environnement, ou le fichier .env.\n"
        f"Plus d'information: {help_file_uri}"
    )


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _upload_file(api_key: str, file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    with file_path.open("rb") as fh:
        response = requests.post(
            f"{API_BASE}/files",
            headers=_headers(api_key),
            data={"purpose": "ocr"},
            files={"file": (file_path.name, fh, mime_type or "application/octet-stream")},
            timeout=120,
        )
    response.raise_for_status()
    payload = response.json()
    file_id = payload.get("id")
    if not file_id:
        raise RuntimeError(f"Réponse upload invalide: {payload}")
    return str(file_id)


def _get_signed_url(api_key: str, file_id: str, expiry_hours: int) -> str:
    response = requests.get(
        f"{API_BASE}/files/{file_id}/url",
        headers=_headers(api_key),
        params={"expiry": expiry_hours},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    signed_url = payload.get("url")
    if not signed_url:
        raise RuntimeError(f"Réponse signed URL invalide: {payload}")
    return str(signed_url)


def _run_ocr(api_key: str, model: str, document_url: str, include_image_base64: bool) -> dict[str, Any]:
    return _run_ocr_document(
        api_key,
        model,
        {"type": "document_url", "document_url": document_url},
        include_image_base64,
    )


def _run_ocr_document(
    api_key: str,
    model: str,
    document: dict[str, Any],
    include_image_base64: bool,
) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE}/ocr",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json={
            "model": model,
            "document": document,
            "include_image_base64": include_image_base64,
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def _pdf_file_to_data_url(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:application/pdf;base64,{encoded}"


def _run_ocr_from_pdf_base64(
    api_key: str,
    model: str,
    file_path: Path,
    include_image_base64: bool,
) -> dict[str, Any]:
    return _run_ocr_document(
        api_key,
        model,
        {"type": "document_url", "document_url": _pdf_file_to_data_url(file_path)},
        include_image_base64,
    )


def _build_markdown(ocr_payload: dict[str, Any]) -> str:
    return "\n".join(_iter_page_markdown_chunks(ocr_payload)).strip() + "\n" if ocr_payload.get("pages") else ""


def _iter_page_markdown_chunks(ocr_payload: dict[str, Any]) -> list[str]:
    pages = ocr_payload.get("pages", [])
    chunks: list[str] = []
    for i, page in enumerate(pages, start=1):
        markdown = page.get("markdown", "")
        if markdown:
            chunks.append(f"<!-- page {i} -->\n{markdown.strip()}\n")
    return chunks


def _load_ocr_payload(json_path: Path) -> dict[str, Any]:
    if not json_path.exists():
        raise FileNotFoundError(f"JSON OCR introuvable: {json_path}")
    return json.loads(json_path.read_text(encoding="utf-8"))


def _image_output_name(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    name = Path(value).name
    return name or fallback


def _default_images_output_dir(pdf_path: Path) -> Path:
    return pdf_path.with_name(f"{pdf_path.stem}_ocr_images")


def _markdown_image_dir(markdown_output: Path, images_output_dir: Path) -> str:
    relative_dir = os.path.relpath(images_output_dir, start=markdown_output.parent)
    return Path(relative_dir).as_posix()


def _rewrite_markdown_image_links(
    markdown: str,
    ocr_payload: dict[str, Any],
    markdown_output: Path,
    images_output_dir: Path,
) -> str:
    image_dir = _markdown_image_dir(markdown_output, images_output_dir)
    image_ids = {
        str(image_data.get("id"))
        for page in ocr_payload.get("pages", [])
        for image_data in (page.get("images") or [])
        if image_data.get("id")
    }
    if not image_ids:
        return markdown

    rewritten_markdown = markdown
    for image_id in sorted(image_ids):
        replacement = posixpath.join(image_dir, image_id)
        rewritten_markdown = rewritten_markdown.replace(f"]({image_id})", f"]({replacement})")
    return rewritten_markdown


def _write_markdown_output(markdown_output: Path, markdown: str) -> None:
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(markdown, encoding="utf-8")
    print(f"Markdown extrait écrit: {markdown_output}")


def _bbox_to_pdf_rect(
    bbox: dict[str, Any],
    page_rect: Any,
    ocr_width: float,
    ocr_height: float,
) -> Any:
    if ocr_width <= 0 or ocr_height <= 0:
        raise ValueError("Dimensions OCR invalides pour convertir une bounding box.")

    x0 = float(bbox["top_left_x"]) / ocr_width * float(page_rect.width)
    y0 = float(bbox["top_left_y"]) / ocr_height * float(page_rect.height)
    x1 = float(bbox["bottom_right_x"]) / ocr_width * float(page_rect.width)
    y1 = float(bbox["bottom_right_y"]) / ocr_height * float(page_rect.height)

    import fitz

    clip = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    clip = clip & page_rect
    if clip.is_empty or clip.width <= 0 or clip.height <= 0:
        raise ValueError(f"Bounding box hors page ou vide: {bbox}")
    return clip


def _extract_images_from_pdf(
    pdf_path: Path,
    ocr_payload: dict[str, Any],
    output_dir: Path,
    render_dpi: int,
    jpeg_quality: int,
) -> list[Path]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF introuvable: {pdf_path}")
    if render_dpi <= 0:
        raise ValueError("--render-dpi doit être strictement positif.")
    if not 1 <= jpeg_quality <= 100:
        raise ValueError("--jpeg-quality doit être compris entre 1 et 100.")

    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "PyMuPDF est requis pour l'extraction des images. "
            "Installez les dépendances optionnelles (requirements-optional.txt)."
        ) from exc

    pages = ocr_payload.get("pages", [])
    extracted_paths: list[Path] = []

    # Compter le nombre total d'images à extraire
    total_images = sum(len(page_data.get("images") or []) for page_data in pages)

    # Créer le répertoire de sortie uniquement s'il y a des images à extraire
    if total_images > 0:
        output_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(pdf_path) as document:
        if len(document) < len(pages):
            raise RuntimeError(
                f"Le PDF contient {len(document)} page(s), mais le JSON OCR en décrit {len(pages)}."
            )

        for page_index, page_data in enumerate(pages):
            images = page_data.get("images") or []
            if not images:
                continue

            dimensions = page_data.get("dimensions") or {}
            ocr_width = float(dimensions.get("width") or 0)
            ocr_height = float(dimensions.get("height") or 0)
            if ocr_width <= 0 or ocr_height <= 0:
                raise ValueError(f"Dimensions OCR invalides pour la page {page_index + 1}: {dimensions}")

            page = document.load_page(page_index)
            page_rect = page.rect

            for image_index, image_data in enumerate(images, start=1):
                image_name = _image_output_name(image_data.get("id"), f"image-{image_index:02d}.jpg")
                clip = _bbox_to_pdf_rect(image_data, page_rect, ocr_width, ocr_height)
                pixmap = page.get_pixmap(clip=clip, dpi=render_dpi, alpha=False)

                output_path = output_dir / image_name
                pixmap.save(output_path, jpg_quality=jpeg_quality)
                extracted_paths.append(output_path)

    return extracted_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR Mistral AI.")
    parser.add_argument("--api-key", default=os.getenv("MISTRAL_API_KEY"), help="Clé API Mistral.")
    parser.add_argument("--model", default="mistral-ocr-latest", help="Modèle OCR (défaut: mistral-ocr-latest).")
    parser.add_argument("--file", type=Path, help="Chemin local d'un PDF/image à uploader.")
    parser.add_argument("--document-url", help="URL publique du document à OCR.")
    parser.add_argument("--expiry-hours", type=int, default=24, help="Durée de validité de l'URL signée.")
    parser.add_argument("--json-output", type=Path, default=Path("mistral_ocr_output.json"), help="Sortie JSON complète.")
    parser.add_argument("--markdown-output", type=Path, default=Path("mistral_ocr_output.md"), help="Sortie Markdown extraite.")
    parser.add_argument("--include-image-base64", action="store_true", help="Inclure les images pages en base64.")
    parser.add_argument(
        "--no-extract-images",
        action="store_true",
        help="Désactive l'extraction automatique des images JPEG depuis le PDF local (active par défaut quand --file est fourni).",
    )
    parser.add_argument(
        "--extract-images-only",
        action="store_true",
        help="N'exécute pas l'OCR: lit un JSON OCR existant puis extrait les images depuis le PDF local fourni via --file.",
    )
    parser.add_argument(
        "--ocr-json-input",
        type=Path,
        help="JSON OCR existant à relire pour --extract-images-only (défaut: --json-output).",
    )
    parser.add_argument(
        "--images-output-dir",
        type=Path,
        help="Dossier de sortie des JPEG extraits (défaut: <pdf>_ocr_images).",
    )
    parser.add_argument("--render-dpi", type=int, default=200, help="Résolution de rendu pour les JPEG extraits.")
    parser.add_argument("--jpeg-quality", type=int, default=95, help="Qualité JPEG des images extraites (1-100).")
    args = parser.parse_args()

    if args.extract_images_only:
        args.no_extract_images = False  # --extract-images-only implique toujours l'extraction

    extract_images = args.file and not args.no_extract_images

    if extract_images and not args.file:
        raise ValueError("L'extraction d'images nécessite un PDF local fourni via --file.")

    if args.extract_images_only:
        ocr_json_input = args.ocr_json_input or args.json_output
        ocr_payload = _load_ocr_payload(ocr_json_input)
        print(f"JSON OCR lu: {ocr_json_input}")
    else:
        if not args.api_key or not str(args.api_key).strip():
            raise ValueError(_missing_api_key_help_message())
        if bool(args.file) == bool(args.document_url):
            raise ValueError("Fournir exactement une source: --file OU --document-url.")

        if args.file:
            print(f"[1/3] Upload du fichier: {args.file}")
            file_id = _upload_file(args.api_key, args.file)
            print(f"[2/3] Récupération de l'URL signée (file_id={file_id})")
            document_url = _get_signed_url(args.api_key, file_id, args.expiry_hours)
        else:
            document_url = str(args.document_url)

        print(f"[3/3] OCR en cours via {args.model}...")
        ocr_payload = _run_ocr(args.api_key, args.model, document_url, args.include_image_base64)

        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(ocr_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON OCR écrit: {args.json_output}")

    markdown = _build_markdown(ocr_payload)

    if extract_images:
        output_dir = args.images_output_dir or _default_images_output_dir(args.file)
        extracted_images = _extract_images_from_pdf(
            pdf_path=args.file,
            ocr_payload=ocr_payload,
            output_dir=output_dir,
            render_dpi=args.render_dpi,
            jpeg_quality=args.jpeg_quality,
        )
        markdown = _rewrite_markdown_image_links(markdown, ocr_payload, args.markdown_output, output_dir)
        print(f"{len(extracted_images)} image(s) extraite(s) dans: {output_dir}")

    _write_markdown_output(args.markdown_output, markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
