"""Verify F2-I contracts with the F2-G model runtime, without any training.

Checks all data hashes, all feature rows, train-only preprocessing and OD mass.
An untrained forward pass uses one train origin and the complete destination
universe. It produces no optimization, checkpoint or performance metric.
"""
from __future__ import annotations
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import duckdb
import numpy as np
import pandas as pd
import torch
from deepgravity.adapters import load_santiago, resolve_path
from deepgravity.models.deepgravity import NN_MultinomialRegression
from deepgravity.runner import make_dataset


def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''): result.update(chunk)
    return result.hexdigest()


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def verify():
    proposal=ROOT/'deepgravity/data/santiago/processed/f2i/proposal_common_exclusion'
    scenario=read(proposal/'scenario.json')
    contracts=read(proposal/'feature_contracts.json')
    original_features=ROOT/'deepgravity/data/santiago/processed/f2i/v2'
    checked=0
    for directory,manifest in ((proposal,scenario),(proposal,contracts),(original_features,read(original_features/'verification.json'))):
        for relative,expected in manifest['outputs_sha256'].items():
            assert digest(directory/relative)==expected,relative
            checked+=1
    for relative,expected in scenario['source_hashes'].items():
        assert digest(ROOT/relative)==expected,relative
        checked+=1
    torch.set_num_threads(2)
    torch.manual_seed(20260913)
    report={'status':'passed_pending_adoption','created_at':datetime.now(timezone.utc).isoformat(),
            'python':platform.python_version(),'torch':torch.__version__,'checksummed_artifacts':checked,
            'training_started':False,'optimizer_steps':0,'test_origin_evaluation':False,
            'performance_metrics_produced':False,'source_cohort_unchanged':True,
            'contracts':{},'branches':{},'code_sha256':digest(Path(__file__)),
            'scenario_sha256':digest(proposal/'scenario.json'),
            'feature_contracts_sha256':digest(proposal/'feature_contracts.json')}
    connection=duckdb.connect()
    for branch in scenario['branches']:
        od=connection.execute('SELECT * FROM read_parquet(?)',[str(proposal/branch/'od.parquet')]).fetchdf()
        count=int(od.trip_count.sum())
        mass=float(od.expanded_mass.sum())
        assert count==60511977
        assert np.isclose(mass,85774522.407,rtol=0,atol=1e-6)
        assert not od.duplicated(['origin_unit_id','destination_unit_id']).any()
        assert (od.trip_count>0).all() and (od.expanded_mass>=0).all()
        units=pd.read_csv(proposal/branch/'units.csv',dtype={'unit_id':str}).set_index('unit_id')
        partitions=pd.read_csv(proposal/branch/'partitions.csv',dtype={'unit_id':str}).set_index('unit_id')
        assert set(units.index)==set(partitions.index)
        for role in ('origin','destination'):
            grouped=od.groupby(role+'_unit_id')[['trip_count','expanded_mass']].sum()
            grouped.index=grouped.index.astype(str)
            for quantity in ('trip_count','expanded_mass'):
                expected=grouped[quantity].reindex(units.index,fill_value=0).to_numpy()
                actual=units[role+'_'+quantity].to_numpy()
                assert np.allclose(actual,expected,rtol=1e-12,atol=1e-7)
                assert np.allclose(partitions.loc[units.index,role+'_'+quantity],actual,rtol=0,atol=1e-9)
        assert (units.partition==partitions.loc[units.index,'partition']).all()
        if branch=='zona777':
            assert not set(units.index)&{'848','849','852'}
            assert set(units.geometry_source)=={'official_shapezona777'}
        report['branches'][branch]={'units':len(units),'trip_count':count,'expanded_mass':mass,
                                  'od_pairs':len(od),'unit_and_partition_totals_reconciled':True}
    connection.close()
    for name,entry in contracts['contracts'].items():
        config_path=ROOT/entry['config']
        assert digest(config_path)==entry['config_sha256']
        config=read(config_path)
        assert config['mode']=='f2i_contract_check' and config['status']=='proposal_not_adopted'
        bundle=load_santiago(config['data'],config_path.parent,'scientific')
        columns=config['data']['feature_columns']
        scaler=read(resolve_path(config['preprocessing_path'],config_path.parent))
        assert set(scaler['fit_unit_ids'])==set(bundle.partitions['train'])
        assert not set(scaler['fit_unit_ids'])&(set(bundle.partitions['validation'])|set(bundle.partitions['test']))
        model_path=resolve_path(config['data']['features_path'],config_path.parent)
        physical_path=model_path.with_name(model_path.name.replace('_model.csv','_features.csv'))
        physical=pd.read_csv(physical_path,dtype={'unit_id':str}).set_index('unit_id')
        values=physical[columns].to_numpy(dtype=float)
        assert np.isfinite(values).all() and (values>=0).all()
        shares=np.array([c.endswith('_share') for c in columns])
        assert (values[:,shares]<=1+1e-9).all()
        mapped=values.copy()
        mapped[:,~shares]=np.log1p(mapped[:,~shares])
        lookup={unit:i for i,unit in enumerate(physical.index)}
        train=mapped[[lookup[i] for i in scaler['fit_unit_ids']]]
        mean,scale=train.mean(axis=0),train.std(axis=0)
        scale=np.where(scale<=1e-12,1,scale)
        assert np.allclose(mean,scaler['mean'],rtol=0,atol=1e-12)
        assert np.allclose(scale,scaler['scale'],rtol=0,atol=1e-12)
        expected=(mapped-mean)/scale
        loaded=np.array([bundle.features[i] for i in physical.index])
        assert np.allclose(loaded,expected,rtol=1e-10,atol=1e-10)
        assert np.isclose(sum(sum(x.values()) for x in bundle.flows.values()),85774522.407,rtol=0,atol=1e-5)
        origin=bundle.partitions['train'][0]
        dataset=make_dataset(bundle,[origin],{'seed':20260913},training=False)
        x,y,_=dataset[0]
        width=2*len(columns)+1
        assert list(x.shape)==[1,len(bundle.features),width]
        assert torch.isfinite(x).all() and torch.isfinite(y).all()
        model=NN_MultinomialRegression(width,256,'deepgravity',0.0,torch.device('cpu'))
        model.eval()
        with torch.no_grad(): scores=model(x)
        assert list(scores.shape)==[1,len(bundle.features),1] and torch.isfinite(scores).all()
        report['contracts'][name]={'loaded_units':len(bundle.features),'partitions':{k:len(v) for k,v in bundle.partitions.items()},
            'input_shape':list(x.shape),'score_shape':list(scores.shape),'full_destination_support':True,
            'preprocessing_train_only_verified':True,'maximum_preprocessing_error':float(abs(loaded-expected).max()),
            'forward_pass_only':True}
    # Confirm that the original incomplete zonal candidate remains blocked.
    config=read(ROOT/'config/f2i_contract_zona777_paper19.example.json')['data']
    config.update({'units_path':str(ROOT/'docs/verificacion/f2g/F2-G_UNIDADES_ZONA777.csv'),
                   'partitions_path':str(ROOT/'docs/verificacion/f2g/F2-G_PARTICIONES_UNIDADES.csv'),
                   'od_path':str(ROOT/'deepgravity/data/santiago/interim/f2g_spatial/zona777_od.parquet'),
                   'features_path':str(original_features/'zona777/paper19_features.csv')})
    try: load_santiago(config,ROOT/'config','scientific')
    except ValueError as error:
        assert 'missing/nonfinite' in str(error)
        report['original_missing_geometry_guard']=str(error)
    else: raise AssertionError('Original missing geometry must stay blocked')
    report['all_checks_passed']=True
    output=ROOT/'docs/territorio/f2i/F2-I_INTEGRACION_VERIFICADA.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__': verify()
