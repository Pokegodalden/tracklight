"""Step 5 end-to-end boundaries: immutable imports, drafts, upload and export."""
import base64
from collections import Counter
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ps1.baseline_scheduler import construct
from ps1.webapp import Server
from ps1.workspace import BASE, INPUT_SCHEMAS, OUTPUT_SCHEMAS, RunError, Workspace, decode_upload


def input_files():
    return {n: (BASE / '01_data' / n).read_bytes() for n in INPUT_SCHEMAS}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Workspace()
        self.addCleanup(self.workspace.close)

    def test_sample_export_preserves_all_three_files_and_report(self):
        view = self.workspace.sample()
        blob, manifest = self.workspace.export(view['id'])
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for n in OUTPUT_SCHEMAS:
                self.assertEqual(archive.read(n), (BASE / '03_submission_sample' / n).read_bytes())
            self.assertEqual(json.loads(archive.read('validation.json'))['report'], view['validation']['report'])
        self.assertTrue(manifest['round_trip_report_equal'])
        self.assertFalse(manifest['submission_ready'])
        self.assertEqual(manifest['rule_profile']['profile_id'], 'ps1-provisional-0.2.0')
        self.assertEqual(manifest['rule_profile']['source_updates'][0]['commit'], '966c976005db2e3e40a691cff268fdb8f396a5df')

    def test_generator_is_deterministic_and_preserves_parent(self):
        parent = self.workspace.sample()
        original = deepcopy(self.workspace.get(parent['id'])['files'])
        before = deepcopy(parent['model'])
        first = self.workspace.generate(parent['id'])
        second = self.workspace.generate(parent['id'])
        self.assertEqual(first['tables'], second['tables'])
        self.assertEqual(first['construction'], second['construction'])
        self.assertEqual(before, parent['model'])
        self.assertEqual(original, self.workspace.get(parent['id'])['files'])
        self.assertNotEqual(first['id'], parent['id'])
        self.assertEqual(first['parent_id'], parent['id'])
        self.assertEqual(first['input_identity'], parent['input_identity'])

    def test_partial_baseline_is_never_complete_or_score_eligible(self):
        parent = self.workspace.sample()
        run = self.workspace.generate(parent['id'])
        r = run['validation']['report']
        self.assertEqual(run['construction']['status'], 'PARTIAL_DRAFT')
        self.assertEqual(len(run['model']['activities']), 54)
        self.assertEqual(len(run['tables']['SCHEDULE_ACCESS.csv']), 163)
        self.assertEqual(run['construction']['remaining_scaled_units'], 58)
        self.assertEqual(len(run['construction']['unfinished']), 7)
        self.assertFalse(r['metrics']['all_work_complete'])
        self.assertIsNone(r['metrics']['score_decimal'])
        self.assertFalse(run['submission_ready'])
        self.assertEqual(Counter(f['code'] for f in r['findings'] if f['severity']=='violation'),
                         {'incomplete_workload': 7, 'missing_result': 4})
        self.assertEqual(r['physical_night_diagnostic']['status'], 'ASSIGNED_FOR_MODELLED_RELATIONS')
        self.assertTrue(all(row['eclo']==0 for row in run['tables']['SCHEDULE_ACCESS.csv']))
        blob, _ = self.workspace.export(run['id'])
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            self.assertEqual(json.loads(archive.read('construction.json'))['status'], 'PARTIAL_DRAFT')

    def test_zero_capacity_keeps_every_activity_and_no_completion_rows(self):
        model = self.workspace.sample()['model']
        for location in model['locations']:
            location['supply_capacity'] = 0
        generated = construct(model)
        self.assertEqual(generated['tables']['SCHEDULE_ACCESS.csv'], [])
        self.assertEqual(generated['tables']['RESULTS.csv'], [])
        self.assertEqual({u['activity_id'] for u in generated['construction']['unfinished']},
                         {a['activity_id'] for a in model['activities']})
        self.assertTrue(all(u['deferred_weeks_by_reason'] for u in generated['construction']['unfinished']))

    def test_failed_import_cleans_up_and_preserves_existing_run(self):
        sample = self.workspace.sample()
        files = input_files()
        files['01_LINES.csv'] = b'invalid,headers\n'
        with self.assertRaises(RunError):
            self.workspace.create(files, 'A', 'Bad input')
        self.assertEqual(list(self.workspace.runs), [sample['id']])
        self.assertEqual([p.name for p in self.workspace.root.iterdir()], [sample['id']])
        self.workspace.export(sample['id'])

    def test_changed_instance_does_not_rely_on_sample_ids(self):
        files = {n: b.replace(b'ALP', b'RIVER').replace(b'BET', b'CITY').replace(b'A001', b'JOB_NEW')
                 for n, b in input_files().items()}
        uploaded = self.workspace.create(files, 'A', 'Changed input instance')
        self.assertIsNone(uploaded['validation'])
        with self.assertRaises(RunError):
            self.workspace.export(uploaded['id'])
        generated = self.workspace.generate(uploaded['id'])
        self.assertIn('JOB_NEW', [a['activity_id'] for a in generated['model']['activities']])
        self.assertTrue(all('ALP' not in r['location_id'] and 'BET' not in r['location_id']
                            for r in generated['tables']['SCHEDULE_OCCUPANCY.csv']))
        self.workspace.export(generated['id'])

    def test_export_stops_if_displayed_report_differs(self):
        view = self.workspace.sample()
        view['validation']['report']['status'] = 'FORGED'
        with self.assertRaisesRegex(RunError, 'Round-trip'):
            self.workspace.export(view['id'])

    def test_export_stops_if_rule_provenance_differs(self):
        view = self.workspace.sample()
        view['rule_profile']['profile_sha256'] = '0'*64
        with self.assertRaisesRegex(RunError, 'Rule evidence changed'):
            self.workspace.export(view['id'])

    def test_export_stops_if_input_identity_differs(self):
        view = self.workspace.sample()
        view['input_identity'] = '0'*64
        with self.assertRaisesRegex(RunError, 'Input identity changed'):
            self.workspace.export(view['id'])

    def test_changed_source_blocks_work_and_keeps_original_provenance(self):
        view = self.workspace.sample()
        original = deepcopy(view['source_sha256'])
        changed = dict(original, **{'optimizer.py': 'changed'})
        with patch('ps1.workspace.source_fingerprints', return_value=changed):
            for operation in (lambda: self.workspace.export(view['id']), self.workspace.sample,
                              lambda: self.workspace.generate(view['id']),
                              lambda: self.workspace.optimise(view['id'], 'A')):
                with self.subTest(operation=operation), self.assertRaisesRegex(RunError, 'source changed'):
                    operation()
        self.assertEqual(view['source_sha256'], original)
        _, manifest = self.workspace.export(view['id'])
        self.assertEqual(manifest['source_sha256'], original)
        self.assertIn('web/app.js', original)

    def test_solver_publication_rejects_night_conflicts_and_cleans_up(self):
        parent = self.workspace.sample()
        # This sample completes all work and passes weekly checks, but its
        # common-night relations contradict one another. It must not be
        # published as an optimiser result even if the solver wrapper errs.
        before = deepcopy(parent)
        candidate = {'tables': parent['tables'], 'optimisation': {
            'objective_tenths': parent['validation']['report']['metrics']['score_tenths']}}
        with patch('ps1.optimizer.optimise', return_value=candidate):
            with self.assertRaisesRegex(RunError, 'independent validation'):
                self.workspace.optimise(parent['id'], 'A')
        self.assertEqual(parent, before)
        self.assertEqual(list(self.workspace.runs), [parent['id']])
        self.assertEqual([p.name for p in self.workspace.root.iterdir()], [parent['id']])

    def test_solver_publication_handles_uncomputable_metrics(self):
        parent = self.workspace.sample()
        tables = deepcopy(parent['tables'])
        tables['SCHEDULE_ACCESS.csv'][0]['week'] = 999
        candidate = {'tables':tables, 'optimisation':{'objective_tenths':0}}
        with patch('ps1.optimizer.optimise', return_value=candidate), self.assertRaisesRegex(RunError, 'independent validation'):
            self.workspace.optimise(parent['id'], 'A')
        self.assertEqual(list(self.workspace.runs), [parent['id']])
        self.assertEqual([p.name for p in self.workspace.root.iterdir()], [parent['id']])

    def test_upload_rejects_paths_duplicates_and_bad_base64(self):
        files = [{'name': n, 'data': base64.b64encode(b).decode()} for n,b in input_files().items()]
        self.assertEqual(decode_upload(files), input_files())
        for replacement in ({'name':'../01_LINES.csv','data':''}, files[1], {'name':files[0]['name'],'data':'%%%'}):
            with self.subTest(replacement=replacement['name']), self.assertRaises(RunError):
                decode_upload([replacement]+files[1:])

    def test_semantic_invalid_schedule_stays_visible(self):
        sample = self.workspace.sample()
        files = dict(self.workspace.get(sample['id'])['files'])
        # Scenario B upload with RESULTS labelled A: report it, never silently relabel.
        view = self.workspace.create(files, 'B', 'Mismatch')
        self.assertFalse(view['submission_ready'])
        self.assertTrue(any(f['severity']=='violation' for f in view['validation']['report']['findings']))
        self.assertEqual(self.workspace.get(view['id'])['files']['RESULTS.csv'], files['RESULTS.csv'])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server(('127.0.0.1',0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=3)
        cls.server.server_close()

    def request(self, path, body=None, extra=None):
        headers = {'Content-Type':'application/json','X-PS1-Token':self.server.token}
        headers.update(extra or {})
        req = Request(self.url+path, data=None if body is None else json.dumps(body).encode(), headers=headers)
        return urlopen(req, timeout=10)

    def test_import_generate_export_through_public_routes(self):
        files = [{'name':n,'data':base64.b64encode(b).decode()} for n,b in input_files().items()]
        with self.request('/api/import', {'files':files,'scenario':'A'}) as response:
            run = json.load(response)
        with self.request('/api/generate', {'id':run['id']}) as response:
            generated = json.load(response)
        with self.request('/api/export/'+generated['id']) as response:
            self.assertEqual(response.headers['Content-Type'],'application/zip')
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                self.assertFalse(json.loads(archive.read('manifest.json'))['submission_ready'])

    def test_token_origin_and_host_boundaries(self):
        for headers in ({'X-PS1-Token':'wrong'}, {'Origin':'https://unrelated.example'}, {'Host':'unrelated.example'}):
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as caught:
                self.request('/api/sample', {}, headers)
            self.assertEqual(caught.exception.code,403)

    def test_session_recovery_is_read_only_and_requires_token(self):
        with self.request('/api/sample', {}) as response:
            run = json.load(response)
        count = len(self.server.workspace.runs)
        for _ in range(3):
            with self.request('/api/runs', {}) as response:
                summaries = json.load(response)
                self.assertIn({'id':run['id'], 'label':run['label'], 'scenario':'A'}, summaries)
                self.assertTrue(all(set(s) == {'id', 'label', 'scenario'} for s in summaries))
            with self.request('/api/run', {'id':run['id']}) as response:
                self.assertEqual(json.load(response), run)
        self.assertEqual(len(self.server.workspace.runs), count)
        for route in ('/api/runs', '/api/run'):
            with self.subTest(route=route), self.assertRaises(HTTPError) as caught:
                self.request(route, {'id':run['id']}, {'X-PS1-Token':'wrong'})
            self.assertEqual(caught.exception.code, 403)

    def test_optimise_route_rejects_bad_publication_without_replacing_parent(self):
        with self.request('/api/sample', {}) as response:
            parent = json.load(response)
        count = len(self.server.workspace.runs)
        candidate = {'tables':parent['tables'], 'optimisation':{
            'objective_tenths':parent['validation']['report']['metrics']['score_tenths']}}
        with patch('ps1.optimizer.optimise', return_value=candidate), self.assertRaises(HTTPError) as caught:
            self.request('/api/optimise', {'id':parent['id'], 'scenario':'A', 'seconds':1})
        self.assertEqual(caught.exception.code, 400)
        self.assertIn('independent validation', json.load(caught.exception)['error'])
        self.assertEqual(len(self.server.workspace.runs), count)
        self.assertEqual(self.server.workspace.get(parent['id'])['view'], parent)

    def test_import_error_and_missing_run_are_structured(self):
        for path, body in [('/api/import',{'files':[]}),('/api/generate',{'id':'missing'})]:
            with self.assertRaises(HTTPError) as caught:
                self.request(path,body)
            self.assertEqual(caught.exception.code,400)
            self.assertIn('error',json.load(caught.exception))


if __name__ == '__main__':
    unittest.main()
