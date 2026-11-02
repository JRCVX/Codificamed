#!/usr/bin/env python3
"""Descarga, verifica y descomprime los datos públicos de CodiEsp.

Fuentes (CC-BY-4.0):
  - Catálogo CIE-10-D: https://zenodo.org/records/3706838
  - Corpus gold:      https://zenodo.org/records/3837305

El script es idempotente: si el ZIP ya existe y su SHA-256 coincide, no vuelve a
descargarlo. Los datos crudos quedan en ``data/raw/`` y se registran en
``data/raw/MANIFEST.json``.

Uso:
    python scripts/download_data.py
    python scripts/download_data.py --force
    python scripts/download_data.py --downloads-dir /tmp/opencode/codiesp
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "raw"
DEFAULT_DOWNLOADS_DIR = DEFAULT_DATA_DIR / "downloads"

DATASETS: dict[str, dict[str, Any]] = {
    "codiesp_codes": {
        "url": "https://zenodo.org/records/3706838/files/codiesp_codes.zip?download=1",
        "zip_name": "codiesp_codes.zip",
        "sha256": "ed28f25e50fe958d660a07387414e98dbf9f86a172a1c418f11cc1cc449c9b8e",
        "size": 2_002_661,
        "top_level": "codiesp_codes",
        "expected": ["codiesp_codes/codiesp-D_codes.tsv", "codiesp_codes/README.md"],
        "description": "Catálogo CIE-10-D (diagnósticos) de CodiEsp",
    },
    "codiesp_gold": {
        "url": "https://zenodo.org/records/3837305/files/codiesp.zip?download=1",
        "zip_name": "codiesp.zip",
        "sha256": "52b290233906a2eb589ac7b1d9429adeac88f6a9cae8b0d3c180504afbe61688",
        "size": 11_239_591,
        "top_level": "final_dataset_v4_to_publish",
        "expected": [
            "final_dataset_v4_to_publish/train/trainD.tsv",
            "final_dataset_v4_to_publish/dev/devD.tsv",
            "final_dataset_v4_to_publish/test/testD.tsv",
        ],
        "description": "Corpus CodiEsp train/dev/test con anotaciones gold",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected_sha: str, expected_size: int | None = None) -> bool:
    if not path.is_file():
        return False
    if expected_size is not None and path.stat().st_size != expected_size:
        return False
    return sha256_file(path) == expected_sha


def download(url: str, destination: Path, expected_sha: str, expected_size: int) -> None:
    """Descarga con reintento simple y verificación de integridad."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    if partial.exists():
        partial.unlink()

    headers = {"User-Agent": "CodificaMed/0.1 (proyecto academico ESPOCH)"}
    print(f"Descargando {destination.name} ...")
    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=httpx.Timeout(60.0, read=180.0),
        headers=headers,
    ) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", expected_size))
        with partial.open("wb") as handle, tqdm(
            total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=destination.name
        ) as progress:
            for chunk in response.iter_bytes(1024 * 256):
                handle.write(chunk)
                progress.update(len(chunk))

    actual_sha = sha256_file(partial)
    if actual_sha != expected_sha:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 no coincide para {destination.name}: "
            f"esperado {expected_sha}, obtenido {actual_sha}"
        )
    if partial.stat().st_size != expected_size:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Tamaño inesperado para {destination.name}: {partial.stat().st_size} != {expected_size}"
        )
    os.replace(partial, destination)


def safe_extract(zip_path: Path, destination: Path) -> None:
    """Extrae un ZIP evitando path traversal."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Ruta insegura en ZIP: {member.filename}")
        archive.extractall(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga y verifica CodiEsp")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--downloads-dir", type=Path, default=DEFAULT_DOWNLOADS_DIR)
    parser.add_argument("--force", action="store_true", help="Re-descarga y re-extrae")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    downloads_dir = args.downloads_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "project": "CodificaMed",
        "generated_at": datetime.now(UTC).isoformat(),
        "license": "CC-BY-4.0",
        "sources": {},
    }

    for name, spec in DATASETS.items():
        zip_path = downloads_dir / spec["zip_name"]
        print(f"\n[{name}] {spec['description']}")

        if args.force and zip_path.exists():
            zip_path.unlink()
        if args.force:
            shutil.rmtree(data_dir / spec["top_level"], ignore_errors=True)

        if verify_file(zip_path, spec["sha256"], spec["size"]):
            print(f"  ZIP verificado: {zip_path}")
        else:
            if zip_path.exists():
                print("  ZIP corrupto o incompleto; se vuelve a descargar")
                zip_path.unlink()
            download(spec["url"], zip_path, spec["sha256"], spec["size"])
            if not verify_file(zip_path, spec["sha256"], spec["size"]):
                raise RuntimeError(f"Verificación final fallida para {zip_path}")
            print("  ZIP descargado y verificado")

        missing = [p for p in spec["expected"] if not (data_dir / p).is_file()]
        if missing or args.force:
            print("  Extrayendo ...")
            safe_extract(zip_path, data_dir)
            missing = [p for p in spec["expected"] if not (data_dir / p).is_file()]
        if missing:
            raise RuntimeError(f"Faltan archivos esperados tras extraer: {missing}")
        print(f"  Extraído y verificado: {data_dir / spec['top_level']}")

        manifest["sources"][name] = {
            "url": spec["url"],
            "zip": str(zip_path.relative_to(ROOT)) if zip_path.is_relative_to(ROOT) else str(zip_path),
            "sha256": spec["sha256"],
            "size": spec["size"],
            "top_level": spec["top_level"],
            "expected_files": spec["expected"],
            "license": "CC-BY-4.0",
        }

    manifest_path = data_dir / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nManifiesto escrito en {manifest_path}")
    print("Datos listos. Siguiente paso: python scripts/audit_data.py")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
