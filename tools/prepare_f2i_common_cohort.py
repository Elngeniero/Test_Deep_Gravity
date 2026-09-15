"""Prepare, without adopting, a common exclusion scenario for missing zones.

Runs in the F2-G environment. Original F2-C/F2-G artefacts stay immutable.
No trip IDs or individual coordinates are written; only aggregate OD deltas.
"""
from __future__ import annotations
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import duckdb
import h3
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import contains_xy
from shapely.geometry import shape
from shapely.ops import transform, unary_union

ROOT=Path(__file__).resolve().parents[1]
MISSING={'848','849','852'}


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''): value.update(block)
    return value.hexdigest()


def prepare():
    destination=ROOT/'deepgravity/data/santiago/processed/f2i/proposal_common_exclusion'
    if destination.exists() and any(p.is_file() for p in destination.rglob('*')):
        raise FileExistsError(str(destination))
    destination.mkdir(parents=True,exist_ok=True)
    connection=duckdb.connect()
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='1GB'")
    source=(ROOT/'deepgravity/data/santiago/interim/f2c_canonical/service_date=*/canonical.parquet').as_posix()
    rows=connection.execute("SELECT service_date,origin_zone,destination_zone,origin_x,origin_y,destination_x,destination_y,trip_weight FROM read_parquet(?,union_by_name=true) WHERE cohort_class='primary' AND (origin_zone IN ('848','849','852') OR destination_zone IN ('848','849','852'))",[source]).fetchall()
    document=json.loads((ROOT/'docs/territorio/f2d/F2-D_AREA_APROBADA.geojson').read_text(encoding='utf-8'))
    domain=unary_union([shape(f['geometry']) for f in document['features']])
    if abs(domain.bounds[0])<180: domain=transform(Transformer.from_crs(4326,32719,always_xy=True).transform,domain)
    to_wgs=Transformer.from_crs(32719,4326,always_xy=True)
    deltas={b:defaultdict(lambda:[0,0.0]) for b in ('zona777','h3_r7','h3_r8')}
    excluded_count,excluded_mass=0,0.0
    for day,oz,dz,ox,oy,dx,dy,weight in rows:
        if not contains_xy(domain,ox,oy) or not contains_xy(domain,dx,dy): continue
        excluded_count+=1
        excluded_mass+=weight
        olon,olat=to_wgs.transform(ox,oy)
        dlon,dlat=to_wgs.transform(dx,dy)
        for branch in deltas:
            if branch=='zona777': o,d=oz,dz
            else:
                resolution=int(branch[-1])
                o,d=h3.latlng_to_cell(olat,olon,resolution),h3.latlng_to_cell(dlat,dlon,resolution)
            deltas[branch][(str(o),str(d))][0]+=1
            deltas[branch][(str(o),str(d))][1]+=weight
    impact=json.loads((ROOT/'docs/territorio/f2i/F2-I_GEOMETRY_IMPACT.json').read_text(encoding='utf-8'))
    assert excluded_count==impact['unique_affected_trips']==1904
    assert np.isclose(excluded_mass,impact['affected_mass'],rtol=0,atol=1e-8)
    manifest={'status':'proposal_not_adopted','approval':None,'excluded_zones':sorted(MISSING),
              'excluded_trip_count':excluded_count,'excluded_expanded_mass':excluded_mass,
              'rule':'Same source trips removed from all three representations, before OD aggregation; no feature imputation or substitute polygons.',
              'area_and_tile_rules_unchanged':True,'branches':{},'source_hashes':{},'code_sha256':digest(Path(__file__))}
    partition_path=ROOT/'docs/verificacion/f2g/F2-G_PARTICIONES_UNIDADES.csv'
    partitions=pd.read_csv(partition_path,dtype={'unit_id':str})
    manifest['source_hashes'][str(partition_path.relative_to(ROOT))]=digest(partition_path)
    for branch,delta in deltas.items():
        folder=destination/branch
        folder.mkdir(exist_ok=True)
        original=ROOT/('deepgravity/data/santiago/interim/f2g_spatial/'+branch+'_od.parquet')
        units_path=ROOT/('docs/verificacion/f2g/F2-G_UNIDADES_'+branch.upper()+'.csv')
        for path in (original,units_path): manifest['source_hashes'][str(path.relative_to(ROOT))]=digest(path)
        od=connection.execute('SELECT * FROM read_parquet(?)',[str(original)]).fetchdf()
        od['origin_unit_id']=od.origin_unit_id.astype(str)
        od['destination_unit_id']=od.destination_unit_id.astype(str)
        od=od.set_index(['origin_unit_id','destination_unit_id'])
        before_count=int(od.trip_count.sum())
        before_mass=float(od.expanded_mass.sum())
        for pair,(count,mass) in delta.items():
            if pair not in od.index: raise ValueError('Affected OD absent from original '+str(pair))
            od.loc[pair,'trip_count']-=count
            od.loc[pair,'expanded_mass']-=mass
        if (od.trip_count<0).any() or (od.expanded_mass < -1e-7).any(): raise ValueError('Negative OD after common subtraction')
        residual_zero=od.loc[od.trip_count==0,'expanded_mass']
        if len(residual_zero) and abs(residual_zero).max()>1e-7: raise ValueError('Mass/count disagreement')
        od=od[od.trip_count>0].reset_index()
        assert before_count-int(od.trip_count.sum())==excluded_count
        assert np.isclose(before_mass-float(od.expanded_mass.sum()),excluded_mass,rtol=0,atol=1e-6)
        connection.register('candidate_od',od)
        output_sql=str(folder/'od.parquet').replace("'","''")
        connection.execute("COPY candidate_od TO '"+output_sql+"' (FORMAT PARQUET, COMPRESSION ZSTD)")
        connection.unregister('candidate_od')
        units=pd.read_csv(units_path,dtype={'unit_id':str})
        if branch=='zona777': units=units[~units.unit_id.isin(MISSING)].copy()
        for role in ('origin','destination'):
            grouped=od.groupby(role+'_unit_id')[['trip_count','expanded_mass']].sum()
            for quantity in ('trip_count','expanded_mass'):
                units[role+'_'+quantity]=units.unit_id.map(grouped[quantity]).fillna(0)
        units.to_csv(folder/'units.csv',index=False)
        selected=partitions[(partitions.representation==branch)&partitions.unit_id.isin(units.unit_id)].copy()
        for column in ('origin_trip_count','origin_expanded_mass','destination_trip_count','destination_expanded_mass'):
            selected[column]=selected.unit_id.map(units.set_index('unit_id')[column])
        selected.to_csv(folder/'partitions.csv',index=False)
        pd.DataFrame([{'origin_unit_id':o,'destination_unit_id':d,'removed_trip_count':v[0],'removed_expanded_mass':v[1]} for (o,d),v in sorted(delta.items())]).to_csv(folder/'removed_od.csv',index=False)
        manifest['branches'][branch]={'units':len(units),'od_pairs':len(od),'trip_count':int(od.trip_count.sum()),
                                     'expanded_mass':float(od.expanded_mass.sum()),'active_origins':int((units.origin_trip_count>0).sum()),
                                     'train_origins':int(((units.origin_trip_count>0)&(units.partition=='train')).sum())}
    for path,expected in manifest['source_hashes'].items(): assert digest(ROOT/path)==expected
    manifest['original_inputs_unchanged']=True
    manifest['outputs_sha256']={str(p.relative_to(destination)):digest(p) for p in destination.rglob('*') if p.is_file()}
    (destination/'scenario.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/territorio/f2i/F2-I_COMMON_COHORT_PROPOSAL.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest['branches'],indent=2))
    print('COMMON_COHORT_PROPOSAL_READY, NOT ADOPTED')


if __name__=='__main__': prepare()
