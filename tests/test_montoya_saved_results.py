"""Archive consistency checks for the original-XML extension report (no XML needed)."""
from pathlib import Path
import csv

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results/montoya_extension1'


def read(name):
    with (RESULTS/name).open(newline='',encoding='utf8') as handle:
        return list(csv.DictReader(handle))


def test_montoya_extension_results_independent_physical_replay():
    groups=[read('extension1_a_original_xml.csv'),
            read('extension1_e_original_xml.csv'),
            read('extension1_g_original_xml.csv')]
    assert list(map(len,groups))==[5,4,8]
    rows=[r for group in groups for r in group]
    assert sum(r['original_dp_physically_valid']=='True' for r in rows)==2
    assert sum(r['corrected_physically_valid']=='True' for r in rows)==17
    assert all(r['corrected_certified_finite_grid']=='True' for r in rows)
    assert all(float(r['corrected_time_min'])<float(r['original_dp_time_min']) for r in rows)
    assert all('original-XML' in r['provenance'] for r in rows)


def test_original_xml_baseline_against_saved_pilot():
    rows=read('old_baseline_regression_checks.csv')
    assert len(rows)==17
    assert all(r['matched']=='True' for r in rows)


def test_saved_cross_machine_objectives():
    rows=read('cross_machine_objectives.csv')
    assert len(rows)==36
    assert all(r['match_at_1e_6']=='True' for r in rows)


def test_thermal_original_xml_is_labeled_uncalibrated():
    rows=read('thermal_robustness_original_xml.csv')
    assert len(rows)==16
    assert all(r['replay_valid']=='True' and r['grid_certified']=='True' for r in rows)
    assert all('independent-tour' in r['provenance'] for r in rows)


def test_dominance_ablation_exact_objective_equal():
    rows=read('dominance_ablation.csv')
    assert len(rows)==6
    for n in ('10','20','40'):
        subset=[r for r in rows if r['customers']==n]
        assert len(subset)==2
        assert subset[0]['objective_min']==subset[1]['objective_min']
        assert all(r['grid_certified']=='True' and r['feasible']=='True' for r in subset)
