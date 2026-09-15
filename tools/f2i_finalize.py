"""Corrected, versioned F2-I candidates; no training and no silent adoption.

Only geometry is aggregated here. F2-G cohort, OD and partitions are immutable.
The name paper19 identifies an adaptation with 19 location attributes, not a
claim of equivalence to the original article's data construction protocol.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import build_f2i_features as base
import numpy as np
from pyproj import Transformer
from shapely import STRtree, from_wkb, make_valid, union_all
from shapely.geometry import Point
from shapely.ops import transform

POP = 'population_census_2024_per_km2'
FAMILIES = ('transport','food','health','education','retail')
LAND = ('residential','commercial','industrial','retail','natural')
BUILDINGS = ('residential_bldg','commercial_bldg','industrial_bldg')
PAPER19 = (POP, *('landuse_'+x+'_share' for x in LAND),
           *('road_'+x+'_km_per_km2' for x in ('residential','main','other')),
           *(x+suffix for x in FAMILIES for suffix in ('_poi_per_km2','_area_share')))
MACRO20 = (POP, *(x+'_share' for x in BUILDINGS), 'leisure_poi_per_km2','leisure_share',
           *(x+suffix for x in FAMILIES for suffix in ('_poi_per_km2','_area_share')),
           'main_roads_km_per_km2','secondary_roads_km_per_km2','other_poi_per_km2','other_share')
CANDIDATES = {'paper19': PAPER19, 'macro12_geometry20': MACRO20}
OTHER_VALUES = {
    'amenity': ('community_centre','social_facility','police','fire_station','post_office',
                'townhall','courthouse','place_of_worship','toilets','drinking_water',
                'recycling','waste_basket','bench','shelter'),
    'office': ('government','ngo','company','insurance','lawyer'),
    'tourism': ('museum','hotel','hostel','guest_house','information','attraction'),
    'leisure': ('dog_park','marina'),
}
ABSENT = {'', 'no', 'none', 'vacant', 'disused', 'abandoned', 'construction', 'proposed'}


def classify(tags):
    clean = {k:v for k,v in tags.items() if v not in ABSENT}
    facility = base.classify_facility(clean)
    if facility is None:
        building = clean.get('building')
        for family, types in {
            'health': ('hospital','clinic'), 'education': ('school','university','college','kindergarten'),
            'retail': ('retail','supermarket'), 'transport': ('train_station','transportation'),
        }.items():
            if building in types:
                facility = family
                break
    leisure = facility is None and base.classify_leisure(clean)
    other = facility is None and not leisure and any(clean.get(k) in v for k,v in OTHER_VALUES.items())
    return clean, facility, leisure, other


def polygon_parts(geometry):
    if geometry.geom_type in ('Polygon','MultiPolygon'):
        return geometry
    if hasattr(geometry,'geoms'):
        parts = [polygon_parts(g) for g in geometry.geoms]
        return union_all([g for g in parts if not g.is_empty])
    return union_all([])


def union_measure(unit, geometries, magnitude='area', excluded_boundary=None):
    """Clip then union: overlap is never treated as additional area/length."""
    fragments = [g.intersection(unit) for g in geometries if g.intersects(unit)]
    fragments = [g for g in fragments if not g.is_empty]
    merged = union_all(fragments)
    if excluded_boundary is not None and magnitude == 'length':
        merged = merged.difference(excluded_boundary)
    before = sum(getattr(g,magnitude) for g in fragments)
    after = getattr(merged,magnitude)
    return after, max(0.0,before-after)


def assign_point(index, point):
    owners = list(index.containing(point))
    if len(owners) > 1:
        raise ValueError('Point lies inside overlapping units: ' + str(owners))
    return owners[0] if owners else None


def raw_to_features(raw):
    area = raw['unit_area_km2']
    names = tuple(dict.fromkeys(PAPER19+MACRO20))
    if not math.isfinite(area) or area <= 0:
        return {k:math.nan for k in names}
    output = {POP: raw['population_census_2024']/area}
    for name in names:
        if name == POP:
            continue
        if name.endswith('_share'):
            output[name] = raw[name[:-6]+'_area_km2']/area
        elif name.endswith('_poi_per_km2'):
            output[name] = raw[name[:-12]+'_poi_count']/area
        elif name.endswith('_km_per_km2'):
            output[name] = raw[name[:-8]]/area
        else:
            raise ValueError('Unknown feature '+name)
    return output


def fit_preprocessing(rows, columns, training_ids):
    """log1p rates and density, then z-score fitted on train origins only."""
    matrix = np.array([[rows[i][c] for c in columns] for i in training_ids],dtype=float)
    if not len(matrix) or not np.isfinite(matrix).all():
        raise ValueError('Training features incomplete; cannot fit preprocessing')
    rates = np.array([not c.endswith('_share') for c in columns])
    matrix[:,rates] = np.log1p(matrix[:,rates])
    means, deviations = matrix.mean(axis=0), matrix.std(axis=0)
    constant = deviations <= 1e-12
    scales = np.where(constant,1.0,deviations)
    parameters = {'fit_partition':'train', 'fit_unit_ids':list(training_ids), 'ddof':0,
                  'columns':list(columns), 'log1p':rates.tolist(),'mean':means.tolist(),
                  'scale':scales.tolist(),'constant_train_columns':[c for c,b in zip(columns,constant) if b]}
    transformed = {}
    for unit, row in rows.items():
        values = np.array([row[c] for c in columns],dtype=float)
        values[rates] = np.log1p(values[rates])
        transformed[unit] = dict(zip(columns,((values-means)/scales).tolist()))
    return transformed, parameters


def feature_audit(rows, columns, train_ids):
    complete = [i for i,r in rows.items() if all(math.isfinite(r[c]) for c in columns)]
    matrix = np.array([[rows[i][c] for c in columns] for i in complete],dtype=float)
    if np.any(matrix<0):
        raise ValueError('Negative physical feature')
    shares = [i for i,c in enumerate(columns) if c.endswith('_share')]
    if np.any(matrix[:,shares]>1+1e-9):
        raise ValueError('Coverage above one: geometry aggregation failed')
    stats = {c:{'nonzero_units':int(np.sum(matrix[:,i]>0)), 'zero_fraction':float(np.mean(matrix[:,i]==0)),
                'minimum':float(matrix[:,i].min()), 'maximum':float(matrix[:,i].max()),
                'p50':float(np.quantile(matrix[:,i],.5)), 'p95':float(np.quantile(matrix[:,i],.95))}
             for i,c in enumerate(columns)}
    training = np.array([[rows[i][c] for c in columns] for i in train_ids if i in complete])
    active = np.where(training.std(axis=0)>1e-12)[0]
    correlations = np.corrcoef(training[:,active].T)
    pairs=[]
    for a in range(len(active)):
        for b in range(a+1,len(active)):
            if abs(correlations[a,b])>=.95:
                pairs.append({'left':columns[active[a]],'right':columns[active[b]],'pearson_train':float(correlations[a,b])})
    return {'expected_units':len(rows),'finite_units':len(complete),
            'incomplete_units':sorted(set(rows)-set(complete)), 'range_checks_passed':True,
            'statistics':stats, 'high_correlations_train':pairs}


def load_osm_cache(cache, transformer):
    areas, lines, points = defaultdict(list), defaultdict(list), []
    names = defaultdict(list)
    audit = Counter()
    unknown = Counter()
    with sqlite3.connect(cache.as_uri()+'?mode=ro',uri=True) as con:
        metadata = json.loads(con.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])
        for kind,oid,tagtext,wkb in con.execute('SELECT kind,osm_id,tags,wkb FROM objects ORDER BY kind,osm_id'):
            tags, facility, leisure, other = classify(json.loads(tagtext))
            land, building = base.classify_land(tags), base.classify_building(tags)
            road, macro = base.classify_road(tags)
            if kind=='w' and not road:
                continue
            if kind=='a' and not any((land,facility,leisure,other,building)):
                continue
            if kind=='n' and not any((facility,leisure,other)):
                if any(k in tags for k in OTHER_VALUES):
                    unknown.update([k+'='+tags[k] for k in OTHER_VALUES if k in tags])
                continue
            geom = transform(transformer.transform,from_wkb(wkb))
            if not geom.is_valid:
                geom = make_valid(geom)
                audit['geometries_repaired'] += 1
            name = base.normalized_name(tags)
            category = facility or ('leisure' if leisure else ('other' if other else None))
            if kind=='a':
                geom = polygon_parts(geom)
                if geom.is_empty or geom.area<=0:
                    audit['invalid_area_after_repair'] += 1
                    continue
                if land: areas['landuse_'+land].append(geom)
                if facility: areas[facility+'_area'].append(geom)
                # Building footprint is an independent descriptive layer; it is
                # not added to facility land coverage or interpreted as a partition.
                if building: areas[building].append(geom)
                if leisure: areas['leisure'].append(geom)
                if other: areas['other'].append(geom)
                if name and category: names[category].append((name,geom))
                audit['selected_areas'] += 1
            elif kind=='n':
                points.append((category,name,geom,oid))
                audit['selected_points_before_dedup'] += 1
            elif kind=='w':
                lines['road_'+road].append(geom)
                if macro: lines[macro+'_roads'].append(geom)
                audit['selected_lines'] += 1
    name_trees={k:(STRtree([g for _,g in v]),v) for k,v in names.items()}
    selected=[]
    seen=set()
    for category,name,geom,oid in points:
        if name and category in name_trees:
            tree,objects=name_trees[category]
            if any(objects[int(i)][0]==name and objects[int(i)][1].covers(geom) for i in tree.query(geom)):
                audit['named_node_area_duplicates_suppressed'] += 1
                continue
        key=(category,name,geom.wkb)
        if name and key in seen:
            audit['named_coincident_node_duplicates_suppressed'] += 1
            continue
        seen.add(key)
        selected.append((category,geom,oid))
    audit['selected_points_after_dedup']=len(selected)
    return areas,lines,selected,dict(audit,unmapped_point_tags=dict(unknown.most_common(25))),metadata


def dictionary():
    rows=[]
    for column in dict.fromkeys(PAPER19+MACRO20):
        population=column==POP
        share=column.endswith('_share')
        is_road='road' in column
        rows.append({'name':column,'source':'INE Censo 2024' if population else 'OSM Chile 2024-01-01',
            'unit':'persons/km2' if population else ('km2/km2' if share else ('km/km2' if is_road else 'objects/km2')),
            'geometry':'census polygons' if population else ('polygons' if share else ('lines' if is_road else 'points')),
            'aggregation':'areal allocation of population; divide by metric unit area' if population else (
                'area of union of clipped polygons / metric unit area' if share else (
                'length of union of clipped lines; shared boundary assigned to smallest unit_id / metric unit area' if is_road else
                'strictly interior nodes; same-name/category node-area and coincident-node dedup / metric unit area')),
            'null_policy':'missing official unit geometry -> null and blocked; invalid census value -> error; observed absence -> zero',
            'normalization':'identity then train-only z-score' if share else 'log1p then train-only z-score',
            'filter_reference':'F2-I_DICCIONARIO_V2.json:taxonomy and tools/f2i_finalize.py:classify',
            'candidates':[k for k,v in CANDIDATES.items() if column in v]})
    return {'schema':'f2i_geometry_v2','variables':rows,'taxonomy':{
        'facility_priority':['health','education','food','retail','transport'],
        'facility_tags_function':'build_f2i_features.classify_facility, extended by f2i_finalize.classify building types',
        'facility_exact_rules':{
            'health':{'healthcare':'any nonempty value after absent/inactive filtering','amenity':['hospital','clinic','doctors','pharmacy','dentist','veterinary']},
            'education':{'amenity':['school','university','college','kindergarten','library','driving_school','language_school'],'office':['educational_institution']},
            'food':{'amenity':['restaurant','cafe','fast_food','bar','pub','food_court','ice_cream']},
            'retail':{'shop':'any nonempty value after absent/inactive filtering','amenity':['marketplace','bank','bureau_de_change']},
            'transport':{'public_transport':['platform','stop_position','station'],'railway':['station','halt','tram_stop','subway_entrance'],'aeroway':['aerodrome','terminal','gate'],'highway':['bus_stop'],'amenity':['bus_station','ferry_terminal']}},
        'facility_building_fallback_only_if_no_tag_match':{'health':['hospital','clinic'],'education':['school','university','college','kindergarten'],'retail':['retail','supermarket'],'transport':['train_station','transportation']},
        'landuse_exact':list(LAND[:-1]), 'natural_landuse':sorted(base.NATURAL_LANDUSE),
        'natural_values':['wood','scrub','grassland','heath','wetland','water'],
        'roads_residential':sorted(base.RESIDENTIAL_ROADS),'roads_main':sorted(base.MAIN_ROADS),
        'roads_other':sorted(base.OTHER_ROADS),'macro_secondary_roads':sorted(base.SECONDARY_MACRO_ROADS),
        'other_closed_values':OTHER_VALUES,'absent_or_inactive_values':sorted(ABSENT),
        'building_residential':['residential','apartments','house','detached','terrace','semidetached_house','bungalow'],
        'building_commercial':['commercial','office','retail'],'building_industrial':['industrial','warehouse'],
        'leisure':['park','sports_centre','pitch','garden','playground','stadium','fitness_centre']},
        'layer_policy':'Union within each semantic category. Different categories/layers may overlap; their shares must not be summed as an exhaustive land partition.',
        'geometry_policy':'EPSG:32719 metric area and length; H3 cells complete; polygon holes retained; invalid polygons repaired and counted; no generated geometry for absent zone IDs.',
        'limitations':['OSM absence is mapping absence, not proof of real absence.',
            'OSM snapshot is about ten months before November 2024 trips.',
            'Census areal interpolation assumes uniform population within each source polygon.',
            'Named POI deduplication cannot resolve all unnamed or differently named real-world duplicates.',
            'Facility area may denote a campus/site rather than building floor space.',
            'macro12 geometry-safe expansion has 20 location variables (41 pair inputs), not the historical 27-input claim.',
            'paper19 is a Santiago adaptation, not proof of faithful article reproduction.']}


def build_candidates(config_file, output, report_dir, cache):
    if output.exists():
        raise FileExistsError('Immutable F2-I result already exists: '+str(output))
    config=base.load_config(config_file)
    forward=Transformer.from_crs(4326,config['analysis_crs'],always_xy=True)
    expected,geometries,inputs={},{},{}
    for branch,path in config['units'].items():
        unit_path=base.config_path(path,config_file)
        rows=base.unit_rows(unit_path)
        expected[branch]=[r['unit_id'] for r in rows]
        inputs[str(unit_path.relative_to(base.ROOT))]=base.sha256(unit_path)
        if branch=='zona777':
            official=base.zone_geometries(base.config_path(config['geometries'][branch],config_file),forward)
            geometries[branch]={i:official[i] for i in expected[branch] if i in official}
        else:
            geometries[branch]=base.h3_geometries(expected[branch],forward)
    census_path=base.config_path(config['population']['raw_path'],config_file)
    census_hash=base.sha256(census_path)
    census_manifest=json.loads(base.config_path(config['population']['manifest_path'],config_file).read_text(encoding='utf-8'))
    if census_hash != census_manifest['sha256']:
        raise ValueError('Census input hash differs from acquisition manifest')
    inputs['census_sha256']=census_hash
    print('Loading cached OSM geometries and applying explicit taxonomy',flush=True)
    areas,lines,points,osm_audit,osm_manifest=load_osm_cache(cache,forward)
    if base.sha256(base.config_path(config['osm']['raw_path'],config_file)) != osm_manifest['pbf_sha256']:
        raise ValueError('OSM PBF differs from cached source')
    inputs['osm_sha256']=osm_manifest['pbf_sha256']
    inputs['osm_cache_sha256']=base.sha256(cache)
    all_area_names=['landuse_'+x for x in LAND]+[x+'_area' for x in FAMILIES]+list(BUILDINGS)+['leisure','other']
    all_line_names=['road_residential','road_main','road_other','main_roads','secondary_roads']
    area_trees={k:STRtree(v) for k,v in areas.items()}
    line_trees={k:STRtree(v) for k,v in lines.items()}
    partial=output.with_name(output.name+'.partial')
    if partial.exists():
        raise FileExistsError('Partial F2-I build exists: '+str(partial))
    partial.mkdir(parents=True)
    summary={'schema':'f2i_geometry_v2','status':'candidates_verified_selection_pending','created_at':base.utc_now(),
             'inputs':inputs,'osm':osm_audit,'osm_manifest':osm_manifest,'representations':{},'candidate_selection':None,
             'f2j_started':False,'code_sha256':{p.name:base.sha256(p) for p in [Path(__file__),Path(base.__file__),Path(__file__).with_name('f2i_osm_cache.py')]}}
    for branch,ids in expected.items():
        print('Aggregating '+branch,flush=True)
        index=base.UnitIndex(geometries[branch])
        raw={i:{'unit_area_km2':geometries[branch][i].area/1e6 if i in geometries[branch] else math.nan,
                'population_census_2024':0.0,
                **{k+'_area_km2':0.0 for k in all_area_names},
                **{k+'_km':0.0 for k in all_line_names},
                **{k+'_poi_count':0.0 for k in FAMILIES+('leisure','other')}} for i in ids}
        census=base.allocate_census(census_path,index,raw,forward)
        if census['invalid_population_rows'] or census['invalid_geometry_rows']:
            raise ValueError('Invalid census records require explicit resolution')
        if census['allocated_population']>census['source_population']+1e-6:
            raise ValueError('Population mass exceeds source region')
        overlaps=Counter()
        for name,tree in area_trees.items():
            for unit,geom in geometries[branch].items():
                candidates=[areas[name][int(i)] for i in tree.query(geom)]
                value,removed=union_measure(geom,candidates)
                raw[unit][name+'_area_km2']=value/1e6
                overlaps[name+'_overlap_removed_km2']+=removed/1e6
        for unit,geom in geometries[branch].items():
            prior=[other.boundary for other_id,other in index.intersecting(geom) if other_id<unit]
            excluded=union_all(prior) if prior else None
            for name,tree in line_trees.items():
                candidates=[lines[name][int(i)] for i in tree.query(geom)]
                value,removed=union_measure(geom,candidates,'length',excluded)
                raw[unit][name+'_km']=value/1e3
                overlaps[name+'_overlap_removed_km']+=removed/1e3
        point_assignment=Counter()
        for category,point,oid in points:
            unit=assign_point(index,point)
            if unit:
                raw[unit][category+'_poi_count']+=1
                point_assignment['assigned']+=1
            else:
                point_assignment['outside_or_boundary']+=1
        feature_rows={i:raw_to_features(v) for i,v in raw.items()}
        unit_source=base.unit_rows(base.config_path(config['units'][branch],config_file))
        train_ids=[r['unit_id'] for r in unit_source if r['partition']=='train' and int(r['origin_trip_count'])>0 and r['unit_id'] in geometries[branch]]
        folder=partial/branch
        folder.mkdir()
        base.write_candidate(folder/'raw_aggregates.csv',ids,raw,tuple(next(iter(raw.values()))))
        branch_result={'census':census,'overlap_correction':dict(overlaps),
                       'point_assignment':dict(point_assignment),'candidates':{}}
        for candidate,columns in CANDIDATES.items():
            audit=feature_audit(feature_rows,columns,train_ids)
            base.write_candidate(folder/(candidate+'_features.csv'),ids,feature_rows,columns)
            # A partial zone table is retained for audit only. It is never silently
            # fit on fewer units and presented as a complete scientific candidate.
            if not audit['incomplete_units']:
                model_rows,scaler=fit_preprocessing(feature_rows,columns,train_ids)
                base.write_candidate(folder/(candidate+'_model.csv'),ids,model_rows,columns)
                (folder/(candidate+'_preprocessing.json')).write_text(json.dumps(scaler,indent=2)+'\n',encoding='utf-8')
                audit['train_constant_columns']=scaler['constant_train_columns']
            branch_result['candidates'][candidate]=audit
        summary['representations'][branch]=branch_result
    (partial/'feature_dictionary.json').write_text(json.dumps(dictionary(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary['outputs_sha256']={str(p.relative_to(partial)):base.sha256(p) for p in partial.rglob('*') if p.is_file()}
    (partial/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    partial.replace(output)
    report_dir.mkdir(parents=True,exist_ok=True)
    (report_dir/'F2-I_VERIFICACION_V2.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (report_dir/'F2-I_DICCIONARIO_V2.json').write_text(json.dumps(dictionary(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('F2I_CANDIDATES_COMPLETE '+str(output),flush=True)
    print(json.dumps({k:{c:{f:a[f] for f in ('expected_units','finite_units','incomplete_units')} for c,a in v['candidates'].items()} for k,v in summary['representations'].items()},indent=2),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=base.ROOT/'config/f2i_santiago.example.json')
    parser.add_argument('--output',type=Path,default=base.ROOT/'deepgravity/data/santiago/processed/f2i/v2')
    parser.add_argument('--report-dir',type=Path,default=base.ROOT/'docs/territorio/f2i')
    parser.add_argument('--cache',type=Path,default=base.ROOT/'deepgravity/data/santiago/cache/f2i/osm_tagged_v1.sqlite')
    args=parser.parse_args()
    build_candidates(args.config.resolve(),args.output.resolve(),args.report_dir.resolve(),args.cache.resolve())
