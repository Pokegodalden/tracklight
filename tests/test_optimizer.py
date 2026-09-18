"""Small hand-calculated CP-SAT cases, failure states and export boundaries."""
from copy import deepcopy
from datetime import date,timedelta
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ps1.importer import import_directory
from ps1.optimizer import optimise, window_check, objective_gap
from ps1.validator import check_schedule, reconstruct_span
from ps1.workspace import BASE, Workspace


class OptimizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=import_directory(BASE/'01_data')['model']

    def fixture(self,n=1,horizon=4,supply=1):
        m=deepcopy(self.base)
        source_a,source_p=m['activities'][0],m['project_types'][0]
        m['activities'],m['project_types']=[],[]
        m['calendar']['weeks']=horizon
        for l in m['locations']:l['supply_capacity']=supply
        for i in range(n):
            a=dict(source_a,activity_id=f'job{i}',contract_number=f'contract{i}',project_key=[f'contract{i}','Construction'],
                   activity_type='Construction',nature_of_works='Non-live (Others)',access_type='C',
                   start_location_id='SEC:ALP:S01_S02:EB',end_location_id='SEC:ALP:S01_S02:EB',
                   planned_start_date='2027-01-04',predecessor_activity_id=None,workload_units_scaled=2,activity_priority=3)
            p=dict(source_p,contract_number=a['contract_number'],activity_type='Construction',nature_of_activity=a['nature_of_works'],
                   contract_priority=3,access_type='C',number_of_workfronts=1,number_of_maximum_access_per_week=3,
                   planned_completion_date='2027-01-10')
            a['working_span']={'location_ids':sorted(reconstruct_span(a,m))}
            m['activities'].append(a);m['project_types'].append(p)
        return m

    def solve(self,m,scenario='A',**kwargs):
        normalized=deepcopy(m)
        for a in normalized['activities']:
            a['working_span']={'location_ids':sorted(reconstruct_span(a,normalized))}
        result=optimise(normalized,scenario,seconds=kwargs.pop('seconds',3),**kwargs)
        if result['tables']:
            report=check_schedule(m,result['tables'],scenario)
            self.assertTrue(report['metrics']['all_work_complete'])
            self.assertFalse(any(f['severity'] in ('error','violation') for f in report['findings']),report)
            self.assertEqual(report['metrics']['score_tenths'],result['optimisation']['objective_tenths'])
            self.assertFalse(result['optimisation']['full_feasibility_established'])
        return result

    def test_a_complete_sharing_without_excess_or_eclo(self):
        m=self.fixture(4,1)
        r=self.solve(m)
        self.assertEqual(r['optimisation']['status'],'OPTIMAL_MODEL_UNVERIFIED')
        self.assertEqual(r['optimisation']['objective_tenths'],0)
        self.assertEqual(len(r['tables']['SCHEDULE_ACCESS.csv']),4)
        self.assertEqual(len({r['co_share_group'] for r in r['tables']['SCHEDULE_OCCUPANCY.csv']}),1)
        self.assertEqual(r['optimisation']['metrics']['excess_location_week_units'],0)

    def test_illegal_sharing_cannot_make_five_jobs_fit_one_slot(self):
        r=self.solve(self.fixture(5,1))
        self.assertEqual(r['optimisation']['status'],'INFEASIBLE_MODEL')
        self.assertIsNone(r['tables'])

    def test_b_must_use_eclo_to_meet_deadline(self):
        m=self.fixture()
        m['activities'][0]['workload_units_scaled']=3
        r=self.solve(m,'B')
        self.assertEqual(r['optimisation']['objective_tenths'],50)
        self.assertEqual(r['tables']['SCHEDULE_ACCESS.csv'][0]['eclo'],1)
        self.assertEqual(r['optimisation']['metrics']['contract_delay_days'],0)

    def test_b_excess_is_charged_per_location_week(self):
        r=self.solve(self.fixture(1,1,0),'B')
        self.assertEqual(r['optimisation']['metrics']['excess_location_week_units'],3)
        self.assertEqual(r['optimisation']['objective_tenths'],210)

    def test_c_supply_allowance_is_exactly_one(self):
        m=self.fixture(2,1,0)
        for a in m['activities']:a['access_type']='PM'
        for p in m['project_types']:p['access_type']='PM'
        self.assertEqual(self.solve(m,'C')['optimisation']['status'],'INFEASIBLE_MODEL')
        self.assertIsNotNone(self.solve(m,'B')['tables'])

    def test_precedence_cross_contract_blocks_same_week_and_waits(self):
        m=self.fixture(2,2)
        m['activities'][1]['predecessor_activity_id']='job0'
        r=self.solve(m)
        weeks={row['activity_id']:row['week'] for row in r['tables']['SCHEDULE_ACCESS.csv']}
        self.assertEqual(weeks,{'job0':1,'job1':2})
        self.assertEqual(r['optimisation']['objective_tenths'],70)
        self.assertEqual(self.solve(m,'B')['optimisation']['status'],'INFEASIBLE_MODEL')

    def test_contract_workfront_and_weekly_cap(self):
        m=self.fixture(2,1,7)
        m['activities'][1].update(contract_number='contract0',project_key=['contract0','Construction'])
        m['project_types']=m['project_types'][:1]
        m['project_types'][0]['number_of_maximum_access_per_week']=1
        self.assertEqual(self.solve(m)['optimisation']['status'],'INFEASIBLE_MODEL')
        m['project_types'][0]['number_of_workfronts']=2
        self.assertIsNotNone(self.solve(m)['tables'])

    def test_mixed_eclo_sharing_is_not_allowed(self):
        m=self.fixture(2,1,1)
        m['activities'][0]['workload_units_scaled']=3
        r=self.solve(m,'B')
        self.assertEqual([row['eclo'] for row in r['tables']['SCHEDULE_ACCESS.csv']],[1,1])
        self.assertEqual(r['optimisation']['objective_tenths'],100)

    def test_c_windows_independent_and_live_couples_both(self):
        m=self.fixture(2,3,7)
        a,b=m['activities'];a['workload_units_scaled']=9
        b.update(start_location_id='SEC:BET:S11_S12:EB',end_location_id='SEC:BET:S11_S12:EB')
        # Each activity needs an ECLO in each of three weeks: impossible in C.
        self.assertEqual(self.solve(m,'C')['optimisation']['status'],'INFEASIBLE_MODEL')
        a['workload_units_scaled']=3
        m['project_types'][0]['planned_completion_date']='2027-01-10'
        b.update(planned_start_date='2027-01-18',workload_units_scaled=3)
        m['project_types'][1]['planned_completion_date']='2027-01-24'
        r=self.solve(m,'C')
        self.assertEqual(r['optimisation']['c_window_check']['weeks'],{'ALP':[1],'BET':[3]})
        a['nature_of_works']='Live'
        coupled=self.solve(m,'C')
        check=coupled['optimisation']['c_window_check']
        self.assertTrue(check['passed'])
        self.assertGreater(coupled['optimisation']['objective_tenths'],r['optimisation']['objective_tenths'])

    def test_live_core_separation_uses_different_nights(self):
        m=self.fixture(2,1,7)
        m['activities'][0]['nature_of_works']='Live'
        m['activities'][1].update(start_location_id='SEC:ALP:S01_S02:WB',end_location_id='SEC:ALP:S01_S02:WB')
        r=self.solve(m)
        self.assertEqual(len({p['night'] for p in r['optimisation']['abstract_nights']}),2)

    def test_release_shortage_is_a_proven_precheck_not_timeout(self):
        m=self.fixture(1,1)
        m['activities'][0]['planned_start_date']='2027-01-11'
        r=self.solve(m)
        self.assertEqual(r['optimisation']['solver_status'],'PRECHECK_INFEASIBLE')
        self.assertTrue(r['optimisation']['infeasibility_evidence'])
        self.assertIsNone(r['tables'])

    def test_timeout_retains_complete_incumbent(self):
        m=self.fixture(4,2)
        initial=self.solve(m)
        again=self.solve(m,seconds=1e-9,incumbent=initial['tables'])
        self.assertEqual(again['optimisation']['status'],'RETAINED_INCUMBENT_UNVERIFIED')
        self.assertEqual(again['tables'],initial['tables'])
        self.assertFalse(again['optimisation']['model_optimality_proven'])
        self.assertEqual({(p['activity_id'], p['week']) for p in again['optimisation']['abstract_nights']},
                         {(r['activity_id'], r['week']) for r in again['tables']['SCHEDULE_ACCESS.csv']})
        empty=self.solve(m,seconds=1e-9)
        self.assertEqual(empty['optimisation']['status'],'NO_SOLUTION_WITHIN_LIMIT')
        self.assertIsNone(empty['tables'])

    def test_checker_rejection_withholds_candidate(self):
        m=self.fixture()
        from ps1.optimizer import _tables
        def corrupt(*args):
            tables=_tables(*args);tables['SCHEDULE_OCCUPANCY.csv'].clear();return tables
        with patch('ps1.optimizer._tables',side_effect=corrupt), self.assertRaisesRegex(RuntimeError,'independent checker'):
            optimise(m,'A',seconds=3)

    def test_checker_independently_reconstructs_corrupted_working_span(self):
        m=self.fixture()
        m['activities'][0]['working_span']['location_ids']=['PLAT:ALP:S01:EB']
        with self.assertRaisesRegex(RuntimeError,'independent checker'):
            optimise(m,'A',seconds=3)

    def test_argument_limits_and_input_immutability(self):
        m=self.fixture();before=deepcopy(m)
        self.solve(m)
        self.assertEqual(m,before)
        for kwargs in ({'seconds':0},{'seconds':True},{'seconds':float('nan')},{'workers':0},{'seed':-1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):optimise(m,'A',**kwargs)
        with self.assertRaises(ValueError):optimise(m,'D')

    def test_contradictory_bound_cannot_be_reported_as_zero_gap(self):
        self.assertEqual(objective_gap(100, 50), .5)
        self.assertEqual(objective_gap(0, 0), 0)
        for bound in (101, float('nan'), float('inf')):
            with self.subTest(bound=bound), self.assertRaisesRegex(RuntimeError, 'bound contradicts'):
                objective_gap(100, bound)


if __name__=='__main__':unittest.main()
