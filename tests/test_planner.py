"""Planner boundaries: real tiny CSV instances, independent checks and review identity."""
import base64
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ps1.workspace import BASE, INPUT_SCHEMAS, Workspace, RunError, csv_bytes
from ps1.importer import sha
from ps1.webapp import Server
from ps1.planner import compare


def encoded_csv(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\r\n')
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode()


def tiny_inputs():
    files = {n: (BASE/'01_data'/n).read_bytes() for n in INPUT_SCHEMAS}
    project = next(csv.DictReader(io.StringIO(files['07_PROJECT_DETAILS.csv'].decode())))
    project['planned_completion_date'] = '2027-01-10'
    files['07_PROJECT_DETAILS.csv'] = encoded_csv([project])
    activity = next(csv.DictReader(io.StringIO(files['08_ACTIVITY_DETAILS.csv'].decode())))
    activity.update(total_accesses='1', planned_start_date='2027-01-04', predecessor_activity_id='')
    files['08_ACTIVITY_DETAILS.csv'] = encoded_csv([activity, dict(activity, activity_id='A002')])
    files['06_PARAMETERS.csv'] = b'key,value\r\nhorizon_start,2027-01-04\r\nhorizon_weeks,2\r\n'
    return files


def plan_files(workspace, inputs, conflict=False, second_week=False, scenario='A', eclo=0):
    files = dict(workspace.get(inputs['id'])['files'])
    access, occupancy = [], []
    for i, a in enumerate(inputs['model']['activities']):
        week = 2 if second_week and i else 1
        access.append(dict(activity_id=a['activity_id'], access_seq=1, week=week, eclo=eclo, access_night=1))
        span = a['working_span']['location_ids']
        for location in span:
            group = ('other' if conflict and i and location == span[-1] else 'together')
            occupancy.append(dict(activity_id=a['activity_id'], week=week, location_id=location, co_share_group=group))
    tables = {'RESULTS.csv': [dict(scenario=scenario, contract_number='C001',
               simulated_completion_date='2027-01-17' if second_week else '2027-01-10', overrun_days=7 if second_week else 0)],
              'SCHEDULE_ACCESS.csv': access, 'SCHEDULE_OCCUPANCY.csv': occupancy}
    files.update({n: csv_bytes(n, rows) for n, rows in tables.items()})
    return files


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.w = Workspace(); self.addCleanup(self.w.close)
        self.inputs = self.w.create(tiny_inputs(), 'A', 'Tiny inputs')

    def plan(self, **kwargs):
        return self.w.create(plan_files(self.w, self.inputs, **kwargs), kwargs.get('scenario', 'A'), 'Tiny schedule')

    def test_conflict_explains_equality_and_separation_with_scoped_partners(self):
        run = self.plan(conflict=True)
        self.assertEqual(run['planning']['summary']['weekly_violations'], 0)
        self.assertFalse(run['planning']['summary']['checked_model_plan'])
        conflict = next(c for c in run['planning']['conflicts'] if c['kind'] == 'night')
        self.assertIn('must share one night', conflict['explanation'])
        self.assertIn('different nights', conflict['explanation'])
        self.assertTrue(conflict['actionable'])
        self.assertTrue(run['planning']['activities']['A001']['sharing'])
        self.assertTrue(all(s['partners'] == ['A002'] for s in run['planning']['activities']['A001']['sharing']))

    def test_checked_alternative_preserves_parent_and_records_actual_changes(self):
        parent = self.plan(conflict=True); before = deepcopy(parent)
        conflict = next(c for c in parent['planning']['conflicts'] if c['kind'] == 'night')
        candidate = self.w.alternative(parent['id'], parent['schedule_snapshot']['version'], conflict['id'], seconds=2)
        self.assertEqual(parent, before)
        self.assertEqual(candidate['alternative']['status'], 'CHECKED_MODEL_ALTERNATIVE')
        comparison = candidate['alternative']['comparison']
        self.assertTrue(comparison['after']['checked_model_plan'])
        self.assertGreater(comparison['changed_activity_count'], 0)
        self.assertEqual(comparison['after']['night_conflict_weeks'], 0)
        self.assertFalse(candidate['submission_ready'])
        self.assertEqual(candidate['planner_review']['records'], [])

    def test_unresolved_and_stale_requests_do_not_create_alternatives(self):
        run = self.plan(conflict=True)
        unresolved = next(c for c in run['planning']['conflicts'] if not c['actionable'])
        with self.assertRaisesRegex(RunError, 'clarification'):
            self.w.alternative(run['id'], run['schedule_snapshot']['version'], unresolved['id'])
        with self.assertRaisesRegex(RunError, 'version differs'):
            self.w.alternative(run['id'], 'stale', unresolved['id'])
        self.assertEqual(len(self.w.runs), 2)

    def test_timeout_is_not_a_checked_alternative(self):
        parent = self.plan(conflict=True)
        conflict = next(c for c in parent['planning']['conflicts'] if c['kind'] == 'night')
        result = self.w.alternative(parent['id'], parent['schedule_snapshot']['version'], conflict['id'], seconds=1e-9)
        self.assertIsNone(result['tables'])
        self.assertEqual(result['alternative']['status'], 'NO_CHECKED_ALTERNATIVE')
        self.assertIsNone(result['alternative']['comparison'])
        self.assertIn(parent['id'], self.w.runs)

    def test_group_renaming_does_not_invent_changed_allocations(self):
        base = self.plan()
        files = dict(self.w.get(base['id'])['files'])
        files['SCHEDULE_OCCUPANCY.csv'] = files['SCHEDULE_OCCUPANCY.csv'].replace(b'together', b'renamed')
        other = self.w.create(files, 'A', 'Renamed groups')
        report = self.w.compare(base['id'], other['id'])
        self.assertEqual(report['changed_activity_count'], 0)
        self.assertNotEqual(base['schedule_snapshot']['version'], other['schedule_snapshot']['version'])

    def test_comparison_reports_delay_and_changed_sharing_partners(self):
        base, other = self.plan(), self.plan(second_week=True)
        report = self.w.compare(base['id'], other['id'])
        self.assertEqual(report['deltas']['activity_delay_days'], 7)
        self.assertEqual(report['after']['completion_date'], '2027-01-17')
        self.assertEqual(report['changed_activity_count'], 2)
        a1 = next(r for r in report['changes'] if r['activity_id'] == 'A001')
        self.assertIn('sharing', a1['changed'])
        self.assertNotIn('accesses', a1['changed'])
        self.assertTrue(report['same_inputs'] and report['same_rules'])

    def test_cross_scenario_comparison_does_not_rank_scores(self):
        base, other = self.plan(), self.plan(scenario='B', eclo=1)
        result = self.w.compare(base['id'], other['id'])
        self.assertFalse(result['scores_comparable'])
        self.assertIsNone(result['deltas']['score'])
        self.assertEqual(result['deltas']['eclo_accesses'], 2)
        self.assertTrue(result['after']['checked_model_plan'])

    def test_score_difference_uses_integer_tenths_before_display(self):
        # Isolated numerical comparison, using 48.3 -> 25.2 from the benchmark.
        base, other = deepcopy(self.plan()), deepcopy(self.plan())
        for view, tenths in ((base, 483), (other, 252)):
            view['validation']['report']['metrics'].update(score_tenths=tenths, activity_weighted_delay_tenths=tenths)
        delta = compare(base, other)['deltas']
        self.assertEqual(delta['score'], -23.1)
        self.assertEqual(delta['weighted_delay'], -23.1)

    def test_live_inspection_shows_only_known_core_and_retains_unverified_scope(self):
        sample = self.w.sample()
        live = next(a for a in sample['model']['activities'] if a['nature_of_works'] == 'Live')
        context = sample['planning']['activities'][live['activity_id']]
        expected = sorted({l.rsplit(':', 1)[0]+(':WB' if l.endswith(':EB') else ':EB') for l in live['working_span']['location_ids']})
        self.assertEqual(context['known_live_mirror_core'], expected)
        self.assertEqual(context['protection_status'], 'UNVERIFIED')

    def test_c_conservative_live_window_blocks_recommendation_even_when_local_checks_pass(self):
        files = tiny_inputs()
        projects = list(csv.DictReader(io.StringIO(files['07_PROJECT_DETAILS.csv'].decode())))
        projects[0]['nature_of_activity'] = 'Live'
        files['07_PROJECT_DETAILS.csv'] = encoded_csv(projects)
        activities = list(csv.DictReader(io.StringIO(files['08_ACTIVITY_DETAILS.csv'].decode())))
        activities[1].update(start_location_id='SEC:ALP:S01_S02:EB', end_location_id='SEC:ALP:S01_S02:EB')
        files['08_ACTIVITY_DETAILS.csv'] = encoded_csv(activities)
        files['06_PARAMETERS.csv'] = b'key,value\r\nhorizon_start,2027-01-04\r\nhorizon_weeks,4\r\n'
        inputs = self.w.create(files, 'C', 'Live inputs')
        files = plan_files(self.w, inputs, scenario='C', eclo=1)
        for name in ('SCHEDULE_ACCESS.csv', 'SCHEDULE_OCCUPANCY.csv'):
            rows = list(csv.DictReader(io.StringIO(files[name].decode())))
            for row in rows:
                if row['activity_id'] == 'A002': row['week'] = '3'
            files[name] = encoded_csv(rows)
        files['RESULTS.csv'] = encoded_csv([{'scenario':'C','contract_number':'C001','simulated_completion_date':'2027-01-24','overrun_days':'14'}])
        run = self.w.create(files, 'C', 'Separated line ECLO weeks')
        s = run['planning']['summary']
        self.assertEqual(s['weekly_violations'], 0)
        self.assertEqual(s['night_status'], 'ASSIGNED_FOR_MODELLED_RELATIONS')
        self.assertFalse(s['c_window_check']['passed'])
        self.assertFalse(s['checked_model_plan'])
        self.assertTrue(next(c for c in run['planning']['conflicts'] if c['id'] == 'model-c-window')['actionable'])
        with self.assertRaisesRegex(RunError, 'recommendation requires'):
            self.w.record_review(run['id'], run['schedule_snapshot']['version'], 'P', 'recommend_for_planning', 'note', 'r1')

    def test_different_input_bytes_rules_or_implementation_block_comparison(self):
        base, other = self.plan(), self.plan()
        for key in ('input_identity', 'rule_profile', 'source_sha256'):
            original = deepcopy(other[key])
            other[key] = 'changed' if key == 'input_identity' else {}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.w.compare(base['id'], other['id'])
            other[key] = original

    def test_incomplete_or_invalid_metrics_are_not_zero_score_or_completed_work(self):
        base = self.plan()
        files = dict(self.w.get(base['id'])['files'])
        files.update({n: csv_bytes(n, []) for n in ('RESULTS.csv', 'SCHEDULE_ACCESS.csv', 'SCHEDULE_OCCUPANCY.csv')})
        incomplete = self.w.create(files, 'A', 'Empty draft')
        result = self.w.compare(base['id'], incomplete['id'])
        self.assertIsNone(result['after']['score'])
        self.assertIsNone(result['deltas']['score'])
        self.assertEqual(result['after']['complete_activities'], 0)
        files = dict(self.w.get(base['id'])['files'])
        rows = deepcopy(base['tables']['SCHEDULE_ACCESS.csv']); rows[0]['week'] = 999
        files['SCHEDULE_ACCESS.csv'] = csv_bytes('SCHEDULE_ACCESS.csv', rows)
        invalid = self.w.create(files, 'A', 'Invalid horizon')
        self.assertIsNone(invalid['planning']['summary']['complete_activities'])
        self.assertFalse(invalid['planning']['summary']['checked_model_plan'])

    def test_review_exact_version_append_only_retry_and_export_hashes(self):
        run = self.plan(); original = deepcopy(self.w.get(run['id'])['files'])
        version = run['schedule_snapshot']['version']
        self.w.record_review(run['id'], version, 'Planner', 'recommend_for_planning', 'Review protection before dispatch.', 'request-1')
        self.w.record_review(run['id'], version, 'Planner', 'recommend_for_planning', 'Review protection before dispatch.', 'request-1')
        self.assertEqual(len(run['planner_review']['records']), 1)
        self.w.record_review(run['id'], version, 'Reviewer 2', 'comment', '<script>literal note</script>', 'request-2')
        self.assertEqual(run['planner_review']['current_decision'], 'recommend_for_planning')
        self.assertEqual(self.w.get(run['id'])['files'], original)
        with self.assertRaisesRegex(RunError, 'different review'):
            self.w.record_review(run['id'], version, 'Planner', 'rejected', 'Changed request', 'request-1')
        blob, manifest = self.w.export(run['id'])
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            self.assertEqual(sha(z.read('planner-review.json')), manifest['planner_review_sha256'])
            review = json.loads(z.read('planner-review.json'))
            self.assertEqual(review['snapshot_version'], version)
            self.assertEqual(len(review['records']), 2)
            self.assertTrue(all(not r['operational_authorisation'] for r in review['records']))
            self.assertEqual(z.read('SCHEDULE_ACCESS.csv'), original['SCHEDULE_ACCESS.csv'])
        self.assertFalse(manifest['submission_ready'])

    def test_review_rejects_stale_empty_and_unchecked_recommendations(self):
        run = self.plan(conflict=True); version = run['schedule_snapshot']['version']
        with self.assertRaisesRegex(RunError, 'version differs'):
            self.w.record_review(run['id'], 'old', 'P', 'comment', 'note', 'r1')
        with self.assertRaisesRegex(RunError, 'recommendation requires'):
            self.w.record_review(run['id'], version, 'P', 'recommend_for_planning', 'note', 'r1')
        with self.assertRaisesRegex(RunError, 'review note'):
            self.w.record_review(run['id'], version, 'P', 'comment', ' ', 'r1')
        with self.assertRaisesRegex(RunError, 'no schedule'):
            self.w.record_review(self.inputs['id'], self.inputs['schedule_snapshot']['version'], 'P', 'comment', 'note', 'r1')
        self.w.record_review(run['id'], version, 'P', 'needs_changes', 'Resolve the night contradiction.', 'r1')
        self.assertEqual(run['planner_review']['current_decision'], 'needs_changes')


class PlannerHTTPTests(unittest.TestCase):
    def test_alternative_comparison_and_review_routes(self):
        with Server(('127.0.0.1', 0)) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            try:
                w = server.workspace
                inputs = w.create(tiny_inputs(), 'A', 'Tiny inputs')
                parent = w.create(plan_files(w, inputs, conflict=True), 'A', 'Conflicting plan')
                conflict = next(c for c in parent['planning']['conflicts'] if c['kind'] == 'night')
                def request(path, body, token=None):
                    req = Request(f'http://127.0.0.1:{server.server_port}'+path, data=json.dumps(body).encode(),
                                  headers={'Content-Type':'application/json', 'X-PS1-Token':token or server.token})
                    with urlopen(req, timeout=10) as response: return json.load(response)
                candidate = request('/api/alternative', {'id':parent['id'], 'version':parent['schedule_snapshot']['version'], 'conflict_id':conflict['id'], 'seconds':2})
                comparison = request('/api/compare', {'base_id':parent['id'], 'candidate_id':candidate['id']})
                self.assertTrue(comparison['after']['checked_model_plan'])
                reviewed = request('/api/review', {'id':candidate['id'], 'version':candidate['schedule_snapshot']['version'], 'reviewer':'Test planner', 'decision':'comment', 'note':'Review only.', 'request_id':'http-1'})
                self.assertEqual(len(reviewed['planner_review']['records']), 1)
                for route in ('/api/alternative', '/api/compare', '/api/review'):
                    with self.subTest(route=route), self.assertRaises(HTTPError) as caught:
                        request(route, {}, token='incorrect')
                    self.assertEqual(caught.exception.code, 403)
            finally:
                server.shutdown(); worker.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
