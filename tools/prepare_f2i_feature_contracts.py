"""Prepare model inputs and reviewable contracts for the unadopted F2-I cohort.

Uses the geospatial Python runtime. It never imports or trains the model.
The generated configs have a non-training mode and require explicit adoption.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import f2i_finalize as final

base=final.base
ROOT=base.ROOT


def prepare():
    proposal=ROOT/'deepgravity/data/santiago/processed/f2i/proposal_common_exclusion'
    scenario=json.loads((proposal/'scenario.json').read_text(encoding='utf-8'))
    manifest_path=proposal/'feature_contracts.json'
    if manifest_path.exists(): raise FileExistsError(str(manifest_path))
    assert scenario['status']=='proposal_not_adopted' and scenario['approval'] is None
    for relative,expected in scenario['outputs_sha256'].items():
        assert base.sha256(proposal/relative)==expected,relative
    report={'status':'verified_proposal_not_adopted','created_at':base.utc_now(),
            'recommendation':{'population':'INE Censo 2024, manzana/entidad, areal interpolation',
                              'main_candidate':'paper19','diagnostic_candidate':'macro12_geometry20',
                              'common_exclusion_trip_count':1904},
            'adoption':None,'training_started':False,'contracts':{},
            'scenario_sha256':base.sha256(proposal/'scenario.json'),
            'feature_build_sha256':base.sha256(ROOT/'deepgravity/data/santiago/processed/f2i/v2/verification.json'),
            'code_sha256':{p.name:base.sha256(p) for p in (Path(__file__),Path(final.__file__),Path(base.__file__))}}
    for branch in scenario['branches']:
        folder=proposal/branch
        units=base.unit_rows(folder/'units.csv')
        ids=[r['unit_id'] for r in units]
        train_ids=[r['unit_id'] for r in units if r['partition']=='train' and float(r['origin_trip_count'])>0]
        for candidate,columns in final.CANDIDATES.items():
            original=ROOT/('deepgravity/data/santiago/processed/f2i/v2/'+branch+'/'+candidate+'_features.csv')
            with original.open(encoding='utf-8') as file:
                rows={r['unit_id']:{c:float(r[c]) for c in columns} for r in csv.DictReader(file) if r['unit_id'] in ids}
            assert set(rows)==set(ids)
            audit=final.feature_audit(rows,columns,train_ids)
            assert audit['finite_units']==len(ids)
            transformed,parameters=final.fit_preprocessing(rows,columns,train_ids)
            base.write_candidate(folder/(candidate+'_features.csv'),ids,rows,columns)
            base.write_candidate(folder/(candidate+'_model.csv'),ids,transformed,columns)
            (folder/(candidate+'_preprocessing.json')).write_text(json.dumps(parameters,indent=2)+'\n',encoding='utf-8')
            prefix='../'+folder.relative_to(ROOT).as_posix()+'/'
            config={'mode':'f2i_contract_check','purpose':'scientific','status':'proposal_not_adopted',
                    'instruction':'This is a verified data-contract proposal. Adopt population, ontology and common cohort before creating any F2-J training config.',
                    'data':{'adapter':'santiago','representation':branch,'od_path':prefix+'od.parquet',
                            'units_path':prefix+'units.csv','partitions_path':prefix+'partitions.csv',
                            'features_path':prefix+candidate+'_model.csv','feature_columns':list(columns),
                            'destination_scope':'global','weight':'expanded_mass'},
                    'preprocessing_path':prefix+candidate+'_preprocessing.json',
                    'scenario_path':'../'+(proposal/'scenario.json').relative_to(ROOT).as_posix(),
                    'location_feature_count':len(columns),'pair_input_count':2*len(columns)+1}
            config_path=ROOT/('config/f2i_contract_'+branch+'_'+candidate+'.example.json')
            if config_path.exists(): raise FileExistsError(str(config_path))
            config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
            report['contracts'][branch+'/'+candidate]={'config':str(config_path.relative_to(ROOT)),
                'config_sha256':base.sha256(config_path),'source_features_sha256':base.sha256(original),
                'units':len(ids),'fit_train_origins':len(train_ids),'pair_input_count':2*len(columns)+1,
                'constant_train_columns':parameters['constant_train_columns'],'coverage':audit}
    expanded=final.dictionary()
    (proposal/'feature_dictionary.json').write_text(json.dumps(expanded,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/territorio/f2i/F2-I_DICCIONARIO_PROPUESTA.json').write_text(json.dumps(expanded,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report['outputs_sha256']={str(p.relative_to(proposal)):base.sha256(p) for p in proposal.rglob('*') if p.is_file()}
    manifest_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/territorio/f2i/F2-I_FEATURE_CONTRACTS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:{f:v[f] for f in ('units','fit_train_origins','pair_input_count','constant_train_columns')} for k,v in report['contracts'].items()},indent=2))
    print('FEATURE_CONTRACTS_READY_NOT_ADOPTED')


if __name__=='__main__': prepare()
