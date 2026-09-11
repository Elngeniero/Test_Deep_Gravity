#!/usr/bin/env python3
"""Fetch and normalize the official DPA 2023 municipal boundaries for RM."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from shapely.geometry import MultiPolygon, Polygon, mapping


SERVICE_URL = "https://ideserver.sma.gob.cl/arcgis/rest/services/IDE/Limites/MapServer/2/query"
SOURCE_DESCRIPTION = (
    "Capa Comunas, Grupo de Trabajo de División Política Administrativa (2023), "
    "publicada por el Servicio de Evaluación Ambiental."
)
FIELDS = ["CUT_REG", "CUT_PROV", "CUT_COM", "REGION", "PROVINCIA", "COMUNA", "SUPERFICIE"]


def signed_area(ring):
    return sum(
        ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    ) / 2.0


def rings_to_geometry(rings):
    """Convert ArcGIS rings into a valid GeoJSON polygon or multipolygon.

    ArcGIS exterior rings share one orientation and interior rings use the opposite.
    The orientation of the largest valid ring establishes which orientation is exterior,
    so the conversion does not assume a clockwise convention.
    """
    polygons = []
    for ring in rings:
        if len(ring) < 4:
            continue
        closed = ring if ring[0] == ring[-1] else ring + [ring[0]]
        polygon = Polygon(closed)
        if not polygon.is_empty and polygon.area > 0:
            polygons.append((closed, polygon, signed_area(closed)))
    if not polygons:
        raise ValueError("Geometría comunal sin anillos válidos.")

    exterior_sign = 1 if max(polygons, key=lambda item: item[1].area)[2] >= 0 else -1
    shells = [(ring, polygon) for ring, polygon, sign in polygons if (1 if sign >= 0 else -1) == exterior_sign]
    holes = [(ring, polygon) for ring, polygon, sign in polygons if (1 if sign >= 0 else -1) != exterior_sign]
    assembled = []
    for shell_ring, shell in shells:
        shell_holes = []
        for hole_ring, hole in holes:
            if shell.contains(hole.representative_point()):
                candidates = [candidate for _, candidate in shells if candidate.contains(hole.representative_point())]
                if shell.area == min(candidate.area for candidate in candidates):
                    shell_holes.append(hole_ring)
        assembled.append(Polygon(shell_ring, shell_holes))
    geometry = assembled[0] if len(assembled) == 1 else MultiPolygon(assembled)
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError("No se pudo construir una geometría comunal válida.")
    return geometry


def fetch_feature_set():
    query = urlencode(
        {
            "where": "CUT_REG='13'",
            "outFields": ",".join(FIELDS),
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        }
    )
    source_url = "{}?{}".format(SERVICE_URL, query)
    response = requests.get(source_url, headers={"User-Agent": "DeepGravity-F2D/1.0"}, timeout=120)
    response.raise_for_status()
    payload = response.content
    data = response.json()
    if "error" in data:
        raise RuntimeError("El servicio DPA respondió: {}".format(data["error"]))
    if data.get("geometryType") != "esriGeometryPolygon" or not data.get("features"):
        raise RuntimeError("El servicio DPA no devolvió polígonos comunales.")
    return data, payload, source_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("deepgravity/data/santiago/reference/comunas_rm_dpa_2023.geojson"),
    )
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--force", action="store_true", help="Permite reemplazar una descarga existente.")
    args = parser.parse_args()
    metadata_path = args.metadata or args.output.with_name(args.output.stem + "_metadata.json")
    if (args.output.exists() or metadata_path.exists()) and not args.force:
        raise FileExistsError("Ya existe una descarga DPA. Use --force solo para actualizarla conscientemente.")

    feature_set, source_payload, source_url = fetch_feature_set()
    features = []
    for feature in feature_set["features"]:
        attributes = feature.get("attributes") or {}
        if set(FIELDS) - set(attributes) or not feature.get("geometry", {}).get("rings"):
            raise ValueError("Una entidad DPA no incluye atributos o geometría esperados.")
        features.append(
            {
                "type": "Feature",
                "properties": {key: attributes[key] for key in FIELDS},
                "geometry": mapping(rings_to_geometry(feature["geometry"]["rings"])),
            }
        )
    if len(features) != 52:
        raise ValueError("Se esperaban 52 comunas de la RM y se recibieron {}.".format(len(features)))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = {"type": "FeatureCollection", "name": "comunas_rm_dpa_2023", "features": features}
    args.output.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    metadata = {
        "dataset": "comunas_rm_dpa_2023",
        "source_description": SOURCE_DESCRIPTION,
        "source_url": source_url,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "source_response_sha256": hashlib.sha256(source_payload).hexdigest(),
        "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "crs": "EPSG:4326",
        "feature_count": len(features),
        "fields": FIELDS,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written={}".format(args.output))
    print("metadata={}".format(metadata_path))
    print("features={}".format(len(features)))


if __name__ == "__main__":
    main()
