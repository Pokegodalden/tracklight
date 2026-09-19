"""Controlled disruptions tested against real schedules and exported decisions."""
from copy import deepcopy
import io
import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile

from test_planner import tiny_inputs, encoded_csv, plan_files
from ps1.workspace import Workspace, RunError, INPUT_SCHEMAS
from ps1.schema import SCHEMAS
from ps1 import planner
from ps1.replan import audit
from ps1.webapp import Server
from ps1.validator import validate_schedule


class ReplanTests(unittest.TestCase):
    def setUp(self):
        self.w = Workspace(); self.addCleanup(self.w.close)
        self.inputs = self.w.create(tiny_inputs(), 'A', 'Tiny inputs')
        self.parent = self.w.create(plan_files(self.w,self.inputs), 'A', 'Parent')

    def revise(self, changes=None, locks=None, cutoff=0, parent=None, **kwargs):
        p = parent or self.parent
        return self.w.replan(p['id'], p['schedule_snapshot']['version'],
                             {'completed_through_week':cutoff, 'locked_activity_ids':locks or [], 'changes':changes or []},
                             seconds=kwargs.pop('seconds', 2), workers=1, **kwargs)

    def growth(self):
        return [{'type':'workload','activity_id':'A001','additional_units':1}]

    def urgent(self, **kwargs):
        a = self.parent['model']['activities'][0]
        fields = {k:a[k] for k in SCHEMAS['08_ACTIVITY_DETAILS.csv']}
        fields.update(activity_id='URGENT01', planned_start_date='2027-01-11', total_accesses=1, **kwargs)
        return [{'type':'urgent_activity', 'activity':fields}]

    def supply(self, week=1):
        return [{'type':'weekly_supply','location_id':self.parent['model']['activities'][0]['start_location_id'], 'week':week, 'capacity':0}]

    def test_growth_preserves_parent_and_minimises_churn_after_score(self):
        original=deepcopy(self.w.get(self.parent['id'])['files'])
        child=self.revise(self.growth())
        self.assertTrue(child['planning']['summary']['checked_model_plan'])
        self.assertTrue(child['optimisation']['churn_optimality_proven'])
        self.assertEqual(child['optimisation']['changed_activity_count'],1)
        self.assertEqual(child['replanning']['comparison']['changed_activity_count'],1)
        self.assertEqual(self.w.get(self.parent['id'])['files'],original)
        self.assertNotEqual(child['input_identity'],self.parent['input_identity'])
        self.assertFalse(child['replanning']['comparison']['scores_comparable'])
        self.assertIsNone(child['replanning']['comparison']['deltas']['score'])
        self.assertEqual(self.w.rollback(child['id'],child['schedule_snapshot']['version']),self.parent)
        self.assertIn(child['id'],self.w.runs)

    def test_supply_reduction_moves_both_shared_jobs_with_unchanged_csv_identity(self):
        child=self.revise(self.supply())
        self.assertEqual(child['input_identity'],self.parent['input_identity'])
        self.assertNotEqual(child['schedule_snapshot']['version'],self.parent['schedule_snapshot']['version'])
        self.assertEqual({r['week'] for r in child['tables']['SCHEDULE_ACCESS.csv']},{2})
        self.assertFalse(child['replanning']['comparison']['same_planning_context'])
        self.assertFalse(child['replanning']['comparison']['scores_comparable'])
        self.assertEqual(self.w.compare(child['id'],self.parent['id'])['candidate_run_id'],child['id'])

    def test_b_and_c_keep_their_excess_policies_under_weekly_nominal_supply(self):
        for scenario in ('B','C'):
            with self.subTest(scenario=scenario):
                parent=self.w.create(plan_files(self.w,self.inputs,scenario=scenario),scenario,'Policy '+scenario)
                child=self.revise(self.supply(),parent=parent,locks=['A001'])
                self.assertTrue(child['planning']['summary']['checked_model_plan'])
                self.assertEqual(child['planning']['summary']['excess_slots'],1)
                self.assertEqual(child['planning']['summary']['score'],7)
                self.assertEqual(child['optimisation']['changed_activity_count'],0)
                self.assertTrue(child['replanning']['lock_audit']['passed'])

    def test_primary_objective_precedes_preserving_an_inferior_parent(self):
        parent=self.w.create(plan_files(self.w,self.inputs,second_week=True),'A','Late parent')
        location=next(l['location_id'] for l in parent['model']['locations'] if l['location_id'] not in parent['model']['activities'][0]['working_span']['location_ids'])
        child=self.revise([{'type':'weekly_supply','location_id':location,'week':2,'capacity':0}],parent=parent)
        self.assertLess(child['planning']['summary']['score'],parent['planning']['summary']['score'])
        self.assertGreater(child['optimisation']['changed_activity_count'],0)
        self.assertTrue(child['optimisation']['churn_optimality_proven'])

    def test_locks_preserve_sharing_partners_and_do_not_invent_local_night_dates(self):
        child=self.revise(self.growth(), locks=['A002'])
        self.assertTrue(child['replanning']['lock_audit']['passed'])
        self.assertEqual(planner.allocation_details(child)['A002'],planner.allocation_details(self.parent)['A002'])
        self.assertEqual(child['optimisation']['changed_activity_count'],1)

    def test_infeasible_locks_are_not_released_and_counterfactual_is_explicit(self):
        child=self.revise(self.supply(), locks=['A001'])
        self.assertIsNone(child['tables'])
        self.assertEqual(child['optimisation']['status'],'INFEASIBLE_MODEL')
        d=child['replanning']['lock_diagnostic']
        self.assertTrue(d['solution_without_explicit_locks'])
        self.assertFalse(d['locks_removed_from_actual_plan'])
        self.assertEqual(child['planning_context']['locked_activity_ids'],['A001'])
        self.assertIsNone(child['replanning']['comparison'])

    def test_urgent_activity_respects_completed_week_and_dependencies(self):
        child=self.revise(self.urgent(predecessor_activity_id='A001'),cutoff=1)
        self.assertTrue(child['planning']['summary']['checked_model_plan'])
        self.assertTrue(child['replanning']['lock_audit']['passed'])
        self.assertEqual(child['planning']['summary']['complete_activities'],3)
        self.assertEqual(child['optimisation']['changed_activity_count'],1)
        self.assertEqual(next(r['week'] for r in child['tables']['SCHEDULE_ACCESS.csv'] if r['activity_id']=='URGENT01'),2)

    def test_partial_activity_completed_prefix_is_frozen_when_workload_grows(self):
        import csv
        files=tiny_inputs(); rows=list(csv.DictReader(io.StringIO(files['08_ACTIVITY_DETAILS.csv'].decode())))
        rows[0]['total_accesses']='2'; files['08_ACTIVITY_DETAILS.csv']=encoded_csv(rows)
        files['06_PARAMETERS.csv']=b'key,value\r\nhorizon_start,2027-01-04\r\nhorizon_weeks,3\r\n'
        inputs=self.w.create(files,'A','Three weeks'); parent=self.w.optimise(inputs['id'],'A',seconds=2,workers=1)
        child=self.revise(self.growth(),parent=parent,cutoff=1)
        self.assertTrue(child['replanning']['lock_audit']['passed'])
        self.assertEqual(child['planning']['summary']['required_units'],4)

    def test_completed_activity_and_past_supply_cannot_be_rewritten(self):
        for changes in (self.growth(),self.supply()):
            with self.assertRaises(ValueError):self.revise(changes,cutoff=1)
        urgent=self.urgent(); urgent[0]['activity']['planned_start_date']='2027-01-04'
        with self.assertRaises(ValueError):self.revise(urgent,cutoff=1)

    def test_unknown_duplicate_and_invalid_proposals_leave_no_children(self):
        count=len(self.w.runs)
        for proposal in ({}, {'changes':[{'type':'unknown'}]}, {'locked_activity_ids':['MISSING']},
                         {'completed_through_week':True}, {'changes':self.growth()*2},
                         {'changes':[{'type':'workload','activity_id':'A001','additional_units':0.1}]},
                         {'changes':[dict(self.supply()[0],capacity=-1)]}):
            with self.assertRaises(ValueError):self.w.replan(self.parent['id'],self.parent['schedule_snapshot']['version'],proposal,seconds=1)
        self.assertEqual(len(self.w.runs),count)

    def test_context_inherits_and_cannot_bypass_locks_through_ordinary_solver(self):
        child=self.revise(locks=['A001'],cutoff=1)
        with self.assertRaises(ValueError):self.revise(locks=[],parent=child,cutoff=1)
        with self.assertRaises(ValueError):self.revise(locks=['A001'],parent=child,cutoff=0)
        with self.assertRaises(RunError):self.w.optimise(child['id'],'A')
        with self.assertRaises(RunError):self.w.generate(child['id'])
        follow=self.w.replan(child['id'],child['schedule_snapshot']['version'],{'changes':self.urgent()},seconds=2,workers=1)
        self.assertEqual(follow['planning_context']['locked_activity_ids'],['A001'])
        self.assertTrue(follow['replanning']['lock_audit']['passed'])

    def test_stale_and_unchecked_parents_rejected(self):
        with self.assertRaises(RunError):self.w.replan(self.parent['id'],'stale',{},seconds=1)
        bad=self.w.create(plan_files(self.w,self.inputs,conflict=True),'A','Conflicted')
        with self.assertRaises(ValueError):self.revise(self.growth(),parent=bad)

    def test_timeout_is_not_infeasibility_and_has_no_fabricated_revision(self):
        child=self.revise(self.growth(),seconds=1e-9)
        self.assertIsNone(child['tables'])
        self.assertEqual(child['optimisation']['status'],'NO_SOLUTION_WITHIN_LIMIT')
        self.assertIsNone(child['replanning']['lock_diagnostic'])

    def test_independent_audit_rejects_added_work_or_changed_partner_in_history(self):
        changed=deepcopy(self.parent)
        changed['tables']['SCHEDULE_ACCESS.csv'][0]['eclo']=1
        self.assertFalse(audit(self.parent,changed,{'completed_through_week':1,'locked_activity_ids':[]})['passed'])
        changed=deepcopy(self.parent)
        changed['tables']['SCHEDULE_OCCUPANCY.csv'][0]['co_share_group']='different'
        self.assertFalse(audit(self.parent,changed,{'completed_through_week':0,'locked_activity_ids':['A001']})['passed'])

    def test_export_retains_changed_inputs_context_and_roundtrip_evidence(self):
        child=self.revise(self.supply())
        raw,manifest=self.w.export(child['id'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn('inputs/08_ACTIVITY_DETAILS.csv',archive.namelist())
            self.assertIn('parent/SCHEDULE_ACCESS.csv',archive.namelist())
            self.assertEqual(json.loads(archive.read('planning-context.json')),child['planning_context'])
            self.assertTrue(json.loads(archive.read('replanning.json'))['lock_audit']['passed'])
            self.assertFalse(manifest['submission_ready'])
        run=self.w.get(child['id'])
        checked=validate_schedule(run['folder']/'inputs',run['folder']/'schedule','A',search_budget=5000,weekly_supply=child['planning_context']['weekly_supply'])
        self.assertEqual(checked['report'],child['validation']['report'])
        child['planning_context']['weekly_supply'][0]['capacity']=1
        with self.assertRaises(RunError):self.w.export(child['id'])

    def test_http_replan_and_rollback_require_session_and_exact_version(self):
        server=Server(('127.0.0.1',0)); self.addCleanup(server.server_close)
        server.workspace.close(); server.workspace=self.w
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.shutdown)
        def post(route,body,token=True):
            headers={'Content-Type':'application/json'}
            if token:headers['X-PS1-Token']=server.token
            with urlopen(Request(f'http://127.0.0.1:{server.server_port}'+route,data=json.dumps(body).encode(),headers=headers),timeout=10) as response:return json.load(response)
        body={'id':self.parent['id'],'version':self.parent['schedule_snapshot']['version'],'proposal':{'changes':self.growth()},'seconds':2}
        with self.assertRaises(HTTPError):post('/api/replan',body,False)
        child=post('/api/replan',body)
        self.assertTrue(child['replanning']['lock_audit']['passed'])
        parent=post('/api/rollback',{'id':child['id'],'version':child['schedule_snapshot']['version']})
        self.assertEqual(parent['id'],self.parent['id'])


if __name__ == '__main__':unittest.main()
