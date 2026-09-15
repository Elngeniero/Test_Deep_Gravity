"""Record an explicitly approved F2-I contract without regenerating or training.

Run in the deepgravity environment only after researcher approval. Historical
proposal files remain immutable; the new record identifies the adopted bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from deepgravity.adapters import load_santiago


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')


def adopt(approval_note):
    proposal = ROOT / 'deepgravity/data/santiago/processed/f2i/proposal_common_exclusion'
    record_path = ROOT / 'docs/territorio/f2i/F2-I_CONTRATO_APROBADO.json'
    destinations = {branch: ROOT / ('config/f2i_approved_' + branch + '_paper19.example.json')
                    for branch in ('zona777', 'h3_r7', 'h3_r8')}
    for path in [record_path, *destinations.values()]:
        if path.exists():
            raise FileExistsError('Approval records are immutable: ' + str(path))
    scenario = read(proposal / 'scenario.json')
    contracts = read(proposal / 'feature_contracts.json')
    integration_path = ROOT / 'docs/territorio/f2i/F2-I_INTEGRACION_VERIFICADA.json'
    integration = read(integration_path)
    if not integration['all_checks_passed'] or integration['training_started']:
        raise ValueError('Expected completed F2-I verification without Santiago training')
    if digest(proposal / 'scenario.json') != integration['scenario_sha256'] or (
            digest(proposal / 'feature_contracts.json') != integration['feature_contracts_sha256']):
        raise ValueError('The proposal differs from the verified integration inputs')
    frozen = {}
    for relative, expected in contracts['outputs_sha256'].items():
        path = proposal / relative
        if digest(path) != expected:
            raise ValueError('Proposal artifact changed: ' + relative)
        frozen[path.relative_to(ROOT).as_posix()] = expected
    for relative, expected in scenario['source_hashes'].items():
        if digest(ROOT / relative) != expected:
            raise ValueError('Original F2-G input changed: ' + relative)
    record = {
        'schema': 'f2i_approved_contract_v1', 'status': 'approved', 'stage': 'F2-I',
        'stage_number': 6, 'stage_status': 'closed',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'approval': {'date_local': '2026-09-14', 'timezone': 'America/Santiago',
                     'actor': 'researcher', 'channel': 'user message in project conversation',
                     'message': approval_note,
                     'approved_scope': 'Censo 2024, corrected paper19 (39 pair inputs), and common exclusion of 1904 trips'},
        'population': {'source': 'INE Censo 2024, manzanas y entidades RM', 'field': 'n_per',
                       'assignment': 'areal interpolation in EPSG:32719; divide by metric unit area',
                       'license': 'CC BY-SA 4.0'},
        'osm': {'source': 'Geofabrik Chile historical extract',
                'snapshot': '2024-01-01T21:21:15Z', 'license': 'ODbL-1.0'},
        'selected_candidate': 'paper19', 'location_feature_count': 19, 'pair_input_count': 39,
        'diagnostic_alternative': {'candidate': 'macro12_geometry20', 'role': 'retained for diagnosis; not the main contract'},
        'cohort': {'excluded_zones': scenario['excluded_zones'],
                   'rule': scenario['rule'], 'excluded_trip_count': 1904,
                   'excluded_expanded_mass': 3140.5316, 'retained_trip_count': 60511977,
                   'retained_expanded_mass': 85774522.407, 'area_and_tile_rules_unchanged': True},
        'normalization': 'log1p on densities/rates; identity on shares; z-score fitted only on active train origins per branch',
        'artifact_root': proposal.relative_to(ROOT).as_posix(),
        'history_policy': 'Proposal files and proposal_not_adopted labels describe the pre-approval snapshot. This record adopts their exact hashes without rewriting them.',
        'f2g_original_inputs_unchanged': True, 'f2j_started': False,
        'next_stage': 'F2-J: small sample, working day and time periods before the stable pilot',
        'gates': {'G4': 'open_until_verified_santiago_pilot', 'G5': 'open'},
        'branches': {}, 'frozen_artifacts_sha256': frozen,
        'original_f2g_inputs_sha256': scenario['source_hashes'],
        'code_sha256': digest(Path(__file__))}
    evidence = [integration_path, proposal / 'feature_contracts.json',
                ROOT / 'docs/territorio/f2i/F2-I_VERIFICACION_V2.json',
                ROOT / 'docs/territorio/f2i/F2-I_DICCIONARIO_PROPUESTA.json']
    record['evidence_sha256'] = {p.relative_to(ROOT).as_posix(): digest(p) for p in evidence}
    configs = {}
    for branch, config_path in destinations.items():
        name = branch + '/paper19'
        prior = contracts['contracts'][name]
        source_config_path = ROOT / prior['config']
        if digest(source_config_path) != prior['config_sha256']:
            raise ValueError('Reviewed configuration changed: ' + name)
        config = read(source_config_path)
        config.update({'status': 'approved',
                       'instruction': 'Approved F2-I data contract. Create stage-specific F2-J subsets and run settings separately; this file does not start training.',
                       'approval_record_path': '../docs/territorio/f2i/F2-I_CONTRATO_APROBADO.json'})
        bundle = load_santiago(config['data'], config_path.parent, 'scientific')
        if len(bundle.features) != scenario['branches'][branch]['units'] or (
                any(len(v) != 19 for v in bundle.features.values())):
            raise ValueError('Approved feature dimensions do not match the verified candidate')
        if not np.isclose(sum(sum(v.values()) for v in bundle.flows.values()),
                          85774522.407, rtol=0, atol=1e-5):
            raise ValueError('Approved mass does not reconcile')
        if bundle.partitions != {k: sorted(bundle.partitions[k]) for k in bundle.partitions}:
            raise ValueError('Unstable partition ordering')
        configs[branch] = config
        record['branches'][branch] = dict(scenario['branches'][branch],
            config=config_path.relative_to(ROOT).as_posix(),
            feature_columns=config['data']['feature_columns'],
            partitions={k: len(v) for k, v in bundle.partitions.items()},
            approved_adapter_load_passed=True,
            source_proposal_config_sha256=prior['config_sha256'])
    for branch, config in configs.items():
        path = destinations[branch]
        write_new(path, config)
        if read(path) != config:
            raise ValueError('Written contract differs from the checked configuration')
        record['branches'][branch]['config_sha256'] = digest(path)
    record['acceptance_checks'] = {
        'proposal_hashes_match_prior_integration': True, 'approved_adapter_loads': 3,
        'source_f2g_hashes_unchanged': True, 'monthly_mass_reconciled_all_branches': True,
        'training_executed_by_adoption': False}
    write_new(record_path, record)
    print(json.dumps({'status': record['status'], 'stage_status': record['stage_status'],
                      'contract': str(record_path), 'branches': record['branches']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval-note', required=True, help='Existing explicit researcher approval; this command does not request it.')
    args = parser.parse_args()
    if not args.approval_note.strip():
        parser.error('An explicit approval note is required')
    adopt(args.approval_note)
