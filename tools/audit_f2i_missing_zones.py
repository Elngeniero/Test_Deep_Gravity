"""Aggregate only the affected canonical trips; never export trip identifiers."""
import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
from pyproj import Transformer
from shapely import STRtree, contains_xy
from shapely.geometry import shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect()
con.execute("SET threads=2")
con.execute("SET memory_limit='1GB'")
source = (ROOT/'deepgravity/data/santiago/interim/f2c_canonical/service_date=*/canonical.parquet').as_posix()
columns = 'service_date, origin_zone, destination_zone, origin_x, origin_y, destination_x, destination_y, trip_weight'
rows = con.execute(f"SELECT {columns} FROM read_parquet(?, union_by_name=true) WHERE cohort_class='primary' AND (origin_zone IN ('848','849','852') OR destination_zone IN ('848','849','852'))", [source]).fetchall()
area_doc = json.loads((ROOT/'docs/territorio/f2d/F2-D_AREA_APROBADA.geojson').read_text(encoding='utf-8'))
parts = [shape(f['geometry']) for f in area_doc['features']]
domain = unary_union(parts)
if abs(domain.bounds[0]) < 180:
    domain = transform(Transformer.from_crs(4326,32719,always_xy=True).transform, domain)
missing = {'848','849','852'}
totals = Counter()
daily = defaultdict(lambda: [0,0.0])
summary = defaultdict(lambda: {'origin_trips':0, 'destination_trips':0, 'origin_mass':0.0, 'destination_mass':0.0})
for day,oz,dz,ox,oy,dx,dy,weight in rows:
    if not contains_xy(domain,ox,oy) or not contains_xy(domain,dx,dy):
        continue
    totals['unique_affected_trips'] += 1
    totals['affected_mass'] += weight
    daily[str(day)][0] += 1
    daily[str(day)][1] += weight
    for role,zone in [('origin',oz),('destination',dz)]:
        if zone in missing:
            summary[zone][role+'_trips'] += 1
            summary[zone][role+'_mass'] += weight
report = dict(totals, by_zone=dict(summary), by_day=dict(daily),
              approved_trip_count=60513881, approved_mass=85777662.9386,
              method='primary canonical trips; strict both endpoints in unchanged F2-D geometry; distinct trip counted once')
report['proposed_common_exclusion'] = {'removed_trip_percent':100*totals['unique_affected_trips']/60513881,
 'remaining_trips':60513881-totals['unique_affected_trips'],
 'remaining_mass':85777662.9386-totals['affected_mass'],
 'removed_mass_percent':100*totals['affected_mass']/85777662.9386,
 'applied':False}
destination=ROOT/'docs/territorio/f2i/F2-I_GEOMETRY_IMPACT.json'
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
