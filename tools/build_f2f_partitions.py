#!/usr/bin/env python3
"""Create deterministic common spatial partitions from completed F2-E aggregates."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


REPRESENTATIONS = ("zona777", "h3_r7", "h3_r8")
PARTITIONS = ("train", "validation", "test")
TARGET_SHARES = np.asarray((0.70, 0.15, 0.15))
TILE_SIZE_M = 15_000
SEED = 20260909


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def unit_source(folder: Path, representation: str) -> Path:
    if representation == "zona777":
        return folder / "F2-E_UNIDADES_ZONA777.csv"
    return folder / "F2-E_UNIDADES_H3_R{}.csv".format(representation.rsplit("r", 1)[1])


def tile_id(xs: pd.Series, ys: pd.Series) -> pd.Series:
    east = np.floor(xs.astype(float) / TILE_SIZE_M).astype(int)
    north = np.floor(ys.astype(float) / TILE_SIZE_M).astype(int)
    return "E" + east.astype(str) + "_N" + north.astype(str)


def stable_noise(tile: str) -> int:
    return int(hashlib.sha256((str(SEED) + "|" + tile).encode("utf-8")).hexdigest()[:12], 16)


def choose_schedule(tile_mass: pd.Series) -> pd.DataFrame:
    """Find the closest 70/15/15 tile allocation, deterministically.

    The study domain spans few 15 km blocks, so an exhaustive allocation makes the
    balance rule transparent rather than relying on an opaque random split.
    """
    tiles = sorted(tile_mass.index.tolist())
    if len(tiles) < 3:
        raise ValueError("Se requieren al menos tres tiles para train/validation/test.")
    masses = tile_mass.reindex(tiles).fillna(0.0).to_numpy(dtype=float)
    total = masses.sum()
    if total <= 0:
        raise ValueError("La masa de origen Zona 777 por tile no puede ser cero.")
    best = None
    if len(tiles) <= 12:
        candidates = itertools.product(range(3), repeat=len(tiles))
    else:
        # Deterministic greedy fallback; unused in the current Santiago domain.
        ordering = sorted(range(len(tiles)), key=lambda i: (-masses[i], stable_noise(tiles[i])))
        assignment = [-1] * len(tiles)
        sums = np.zeros(3)
        for rank, index in enumerate(ordering):
            remaining = len(ordering) - rank
            missing = [value for value in range(3) if value not in assignment]
            choices = missing if remaining == len(missing) else range(3)
            value = min(choices, key=lambda part: ((sums + np.eye(3)[part] * masses[index]) / total - TARGET_SHARES).dot((sums + np.eye(3)[part] * masses[index]) / total - TARGET_SHARES))
            assignment[index] = value
            sums[value] += masses[index]
        candidates = [tuple(assignment)]
    for assignment in candidates:
        if set(assignment) != {0, 1, 2}:
            continue
        sums = np.bincount(assignment, weights=masses, minlength=3)
        counts = np.bincount(assignment, minlength=3)
        loss = float(np.square(sums / total - TARGET_SHARES).sum() + .002 * np.square(counts / len(tiles) - TARGET_SHARES).sum())
        tie = tuple(stable_noise(tiles[i]) for i in range(len(tiles)) if assignment[i] == 2)
        candidate = (loss, tie, assignment, sums, counts)
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise ValueError("No se pudo generar una asignación con tres particiones no vacías.")
    _, _, assignment, sums, counts = best
    return pd.DataFrame({
        "tile_id": tiles,
        "partition": [PARTITIONS[value] for value in assignment],
        "zona777_origin_expanded_mass": masses,
        "target_share": [TARGET_SHARES[value] for value in assignment],
        "actual_share": [sums[value] / total for value in assignment],
        "tile_count_in_partition": [int(counts[value]) for value in assignment],
        "seed": SEED,
        "tile_size_m": TILE_SIZE_M,
    })


def flow_summary(interim: Path, representation: str, assignments: pd.DataFrame) -> pd.DataFrame:
    source = interim / (representation + "_od.parquet")
    if not source.exists():
        return pd.DataFrame([{"representation": representation, "origin_partition": "not_materialized", "destination_partition": "not_materialized", "is_cross_tile": "policy_retained", "trip_count": np.nan, "expanded_mass": np.nan}])
    od = pd.read_parquet(source)
    lookup = assignments[["unit_id", "tile_id", "partition"]].rename(columns={"unit_id": "origin_unit_id", "tile_id": "origin_tile", "partition": "origin_partition"})
    flow = od.merge(lookup, on="origin_unit_id", how="left", validate="many_to_one")
    destination_lookup = assignments[["unit_id", "tile_id", "partition"]].rename(columns={"unit_id": "destination_unit_id", "tile_id": "destination_tile", "partition": "destination_partition"})
    flow = flow.merge(destination_lookup, on="destination_unit_id", how="left", validate="many_to_one")
    if flow[["origin_tile", "destination_tile", "origin_partition", "destination_partition"]].isna().any().any():
        raise ValueError("OD agregada contiene una unidad fuera de la asignación {}.".format(representation))
    flow["is_cross_tile"] = flow.origin_tile != flow.destination_tile
    summary = (flow.groupby(["origin_partition", "destination_partition", "is_cross_tile"], as_index=False)
               .agg(trip_count=("trip_count", "sum"), expanded_mass=("expanded_mass", "sum")))
    summary.insert(0, "representation", representation)
    return summary


def partition_stats(units: pd.DataFrame) -> pd.DataFrame:
    units["is_origin_active"] = units.origin_trip_count > 0
    units["is_destination_active"] = units.destination_trip_count > 0
    rows = []
    for (representation, partition), frame in units.groupby(["representation", "partition"], sort=True):
        origins = frame[frame.is_origin_active]
        destinations = frame[frame.is_destination_active]
        rows.append({
            "representation": representation, "partition": partition,
            "tile_count": frame.tile_id.nunique(), "origin_unit_count": len(origins),
            "destination_unit_count": len(destinations), "origin_trip_count": int(origins.origin_trip_count.sum()),
            "origin_expanded_mass": origins.origin_expanded_mass.sum(),
            "max_unit_bbox_span_m": frame.unit_bbox_span_m.max(),
        })
    return pd.DataFrame(rows)


def audit_legacy(repo: Path) -> dict:
    loader = repo / "deepgravity" / "data_loader.py"
    main = repo / "deepgravity" / "main.py"
    loader_text = loader.read_text(encoding="utf-8")
    main_text = main.read_text(encoding="utf-8")
    required_loader = "all_locs_in_train_region = list(tileid2oa2features2vals[tile_ID].keys())"
    required_main = "train_tiles.csv"
    if required_loader not in loader_text or required_main not in main_text:
        raise ValueError("La auditoría F2-F no reconoce la semántica del código base esperada.")
    return {
        "data_loader": str(loader.as_posix()),
        "loader_destination_scope": "candidate destinations are currently the units in the origin tile",
        "main": str(main.as_posix()),
        "split_artifacts": "train_tiles.csv / test_tiles.csv",
        "required_f2g_change": "use tiles only for disjoint origin splits and retain the approved metropolitan destination universe, including cross-tile flows",
    }


def write_report(path: Path, tiles: pd.DataFrame, stats: pd.DataFrame, flows: pd.DataFrame, max_span: float, legacy: dict) -> None:
    schedule = tiles.groupby("partition", as_index=False).agg(tile_count=("tile_id", "size"), actual_origin_mass_share=("actual_share", "first"))
    materialized = flows[flows.is_cross_tile.isin([True, False])]
    cross = materialized.groupby("representation", as_index=False).agg(total_trip_count=("trip_count", "sum"), cross_tile_trip_count=("trip_count", lambda values: values[materialized.loc[values.index, "is_cross_tile"]].sum()), total_expanded_mass=("expanded_mass", "sum"), cross_tile_mass=("expanded_mass", lambda values: values[materialized.loc[values.index, "is_cross_tile"]].sum()))
    cross["cross_tile_trip_share"] = cross.cross_tile_trip_count / cross.total_trip_count
    cross["cross_tile_mass_share"] = cross.cross_tile_mass / cross.total_expanded_mass
    nl = chr(10)
    text = [
        "# F2-F — Tiles y particiones espaciales reproducibles", "",
        "**Estado:** completada el 9 de septiembre de 2026; segunda mitad de G3.", "",
        "## Regla fijada", "",
        "Un *tile* es un cuadrado de **15.000 m** en EPSG:32719, indexado por `floor(x/15000), floor(y/15000)`. No es una unidad OD. La mayor extensión de una unidad activa es {:.1f} m, inferior al lado del tile; por eso cada bloque supera las unidades Zona 777, H3-r7 y H3-r8 que contiene.".format(max_span),
        "", "La misma cuadrícula y la misma asignación de tiles se usan en las tres representaciones. La agenda se elige una vez mediante la masa originada Zona 777, objetivo 70%/15%/15%, semilla `{}` y búsqueda determinista. No se usa el conjunto de prueba para elegir resolución o hiperparámetros.".format(SEED),
        "", "## Agenda común", "", schedule.to_csv(index=False), "",
        "`F2-F_ASIGNACION_TILES.csv` guarda cada tile y `F2-F_PARTICIONES_UNIDADES.csv` cada unidad activa. Las aserciones de construcción verifican que toda unidad origen aparece una sola vez y que no hay discrepancias de asignación entre ramas.",
        "", "## Flujos que cruzan bloques", "", (cross.to_csv(index=False) if not cross.empty else "La política retiene flujos cruzados; su tabla OD agregada se materializará con el adaptador F2-G."), "",
        "Los destinos quedan permitidos en todo el dominio metropolitano aprobado, incluso si pertenecen a otro tile o a otra partición. La partición se aplica al **origen**; los flujos cruzados se mantienen. Así se evita borrar viajes metropolitanos y se preserva una prueba espacial genuina por origen.",
        "", "## Auditoría del código base y condición para F2-G", "",
        "La auditoría confirma que `{}` limita hoy el universo de destinos a las unidades del tile de origen y que `{}` se apoya en `train_tiles.csv`/`test_tiles.csv`. Esa semántica no implementa todavía este protocolo. F2-G debe cambiarla para que tiles separen orígenes, mientras el universo de candidatos conserva todos los destinos del dominio y los flujos cruzados.".format(legacy["data_loader"], legacy["main"]),
        "", "## Salidas", "",
        "- `F2-F_ESTADISTICAS_PARTICION.csv`: unidades, masa y tamaño por rama y partición.",
        "- `F2-F_FLUJOS_CRUZADOS.csv`: masa y viajes por partición de origen/destino, sin pares OD individuales.",
        "- `F2-F_MANIFIESTO_EJECUCION.json`: parámetros, hashes y resultado de las aserciones.",
    ]
    path.write_text(nl.join(text) + nl, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--f2e", type=Path, default=Path("docs/territorio/f2e"))
    parser.add_argument("--interim", type=Path, default=Path("deepgravity/data/santiago/interim/f2e_spatial"))
    parser.add_argument("--output", type=Path, default=Path("docs/territorio/f2f"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frames = []
    for representation in REPRESENTATIONS:
        frame = pd.read_csv(unit_source(args.f2e, representation))
        frame["representation"] = representation
        frame["tile_id"] = tile_id(frame.unit_x_32719, frame.unit_y_32719)
        frames.append(frame)
    units = pd.concat(frames, ignore_index=True)
    if (units.unit_bbox_span_m >= TILE_SIZE_M).any():
        offenders = units.loc[units.unit_bbox_span_m >= TILE_SIZE_M, ["representation", "unit_id", "unit_bbox_span_m"]]
        raise ValueError("Hay unidades mayores o iguales que el tile: {}".format(offenders.to_dict("records")))
    zone_mass = units.loc[units.representation == "zona777"].groupby("tile_id").origin_expanded_mass.sum()
    all_tiles = sorted(units.tile_id.unique())
    schedule = choose_schedule(zone_mass.reindex(all_tiles, fill_value=0.0))
    units = units.merge(schedule[["tile_id", "partition"]], on="tile_id", how="left", validate="many_to_one")
    if units.partition.isna().any():
        raise ValueError("Existen unidades sin partición.")
    origins = units[units.origin_trip_count > 0]
    if origins.duplicated(["representation", "unit_id"]).any() or not (origins.groupby(["representation", "unit_id"]).partition.nunique() == 1).all():
        raise ValueError("Fuga: una unidad origen aparece en más de una partición.")
    if units.groupby("tile_id").partition.nunique().max() != 1:
        raise ValueError("Un tile tiene más de una partición.")
    assignments = units[["representation", "unit_id", "tile_id", "partition", "origin_trip_count", "origin_expanded_mass", "destination_trip_count", "destination_expanded_mass", "unit_bbox_span_m"]].sort_values(["representation", "unit_id"])
    assignments.to_csv(args.output / "F2-F_PARTICIONES_UNIDADES.csv", index=False)
    schedule.sort_values("tile_id").to_csv(args.output / "F2-F_ASIGNACION_TILES.csv", index=False)
    stats = partition_stats(units)
    stats.to_csv(args.output / "F2-F_ESTADISTICAS_PARTICION.csv", index=False)
    flows = pd.concat([flow_summary(args.interim, representation, units[units.representation == representation]) for representation in REPRESENTATIONS], ignore_index=True)
    flows.to_csv(args.output / "F2-F_FLUJOS_CRUZADOS.csv", index=False)
    legacy = audit_legacy(Path("."))
    write_report(args.output / "F2-F_REPORTE_PARTICIONES.md", schedule, stats, flows, float(units.unit_bbox_span_m.max()), legacy)
    manifest = {
        "stage": "F2-F", "status": "completed", "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "tile_crs": "EPSG:32719", "tile_size_m": TILE_SIZE_M, "tile_index_formula": "floor(x/15000), floor(y/15000)",
        "seed": SEED, "target_shares": dict(zip(PARTITIONS, TARGET_SHARES.tolist())), "partition_role": "origin units only; all approved-domain destinations remain candidates", "cross_tile_flows": "retained", "representations": list(REPRESENTATIONS),
        "assertions": {"each_active_origin_once": True, "one_partition_per_tile": True, "tile_larger_than_all_active_units": True, "same_tile_schedule_across_representations": True},
        "legacy_audit": legacy,
        "inputs": {str(unit_source(args.f2e, value)): digest(unit_source(args.f2e, value)) for value in REPRESENTATIONS},
        "outputs": {name: digest(args.output / name) for name in ["F2-F_PARTICIONES_UNIDADES.csv", "F2-F_ASIGNACION_TILES.csv", "F2-F_ESTADISTICAS_PARTICION.csv", "F2-F_FLUJOS_CRUZADOS.csv", "F2-F_REPORTE_PARTICIONES.md"]},
    }
    (args.output / "F2-F_MANIFIESTO_EJECUCION.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps({"tiles": len(schedule), "max_unit_span_m": float(units.unit_bbox_span_m.max()), "assertions": manifest["assertions"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
