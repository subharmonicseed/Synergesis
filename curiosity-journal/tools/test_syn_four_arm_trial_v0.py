import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('runner', Path(__file__).with_name('syn_four_arm_trial_v0.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixture():
    manifest = {'schema': 'syn-skill-transfer-eval-v0', 'study_id': 'synthetic',
                'model_id': 'mock-local-model-v1', 'arms': list(runner.ARMS),
                'train_task_ids': ['arith-train', 'cal-train'],
                'test_tasks': [{'task_id': 'arith-test', 'domain': 'arithmetic'},
                               {'task_id': 'cal-test', 'domain': 'calendar'}],
                'token_budget_per_arm': 2000}
    train = [{'task_id': 'arith-train', 'domain': 'arithmetic', 'prompt': 'What is 2*3?', 'answer': '6'},
             {'task_id': 'cal-train', 'domain': 'calendar', 'prompt': 'One day after 2025-01-01', 'answer': '2025-01-02'}]
    test = [{'task_id': 'arith-test', 'domain': 'arithmetic', 'prompt': 'What is 4*2?'},
            {'task_id': 'cal-test', 'domain': 'calendar', 'prompt': 'One day after 2026-04-01'}]
    return manifest, train, test

class TestRunner(unittest.TestCase):
    def test_bundling_and_no_oracle(self):
        m, train, test = fixture()
        req = runner.build_requests(m, train, test)
        self.assertEqual(len(req), 8)
        self.assertEqual([x['arm'] for x in req], ['baseline']*2 + ['journal']*2 + ['research']*2 + ['skills']*2)
        self.assertTrue(all('oracle.jsonl' not in x['prompt'] for x in req))
        self.assertNotIn('What is 2*3?', req[0]['prompt'])
        self.assertIn('What is 2*3?', req[2]['prompt'])
        self.assertEqual(req[-1]['skill_ids'], ['human-procedure-calendar-v0'])
    def test_prepare_and_refuse_overwrite(self):
        m, train, test = fixture()
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'new'
            rep = runner.prepare(m, train, test, out)
            self.assertEqual(rep['status'], 'prepared_not_executed')
            self.assertEqual(len((out/'requests.jsonl').read_text().splitlines()), 8)
            with self.assertRaises(runner.TrialError):
                runner.prepare(m, train, test, out)
    def test_run_with_mock_backend_generates_real_records(self):
        m, train, test = fixture()
        with tempfile.TemporaryDirectory() as t:
            req = runner.build_requests(m, train, test)
            def backend(prompt):
                return ('8' if '4*2' in prompt else '2026-04-02'), 13
            result = runner.run(req, m['model_id'], backend, Path(t)/'run')
            rows = [json.loads(x) for x in (Path(t)/'run/attempts.jsonl').read_text().splitlines()]
            self.assertEqual(result['n_attempts'], 8)
            self.assertEqual({r['tokens_used'] for r in rows}, {13})
            self.assertEqual(len([x for x in rows if x['arm']=='skills' and x['skill_ids']]),2)
    def test_reject_oracle_in_test_pack(self):
        m, train, test = fixture()
        test[0]['answer']='8'
        with self.assertRaisesRegex(runner.TrialError,'answers'):
            runner.build_requests(m, train, test)
    def test_reject_exact_prompt_leak(self):
        m, train, test = fixture()
        test[0]['prompt']=train[0]['prompt']
        with self.assertRaisesRegex(runner.TrialError,'leakage'):
            runner.build_requests(m, train, test)
    def test_wrong_model(self):
        m, train, test = fixture()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(runner.TrialError, 'model_id'):
                runner.run(runner.build_requests(m, train, test), 'different', lambda p: ('OK',1), Path(t)/'out')
    def test_bad_token_count_is_not_fabricated(self):
        m, train, test = fixture()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(runner.TrialError, 'invalid backend'):
                runner.run(runner.build_requests(m, train, test),m['model_id'],lambda p:('YES',True),Path(t)/'out')
    def test_untrusted_remote_model_not_accepted(self):
        for name in ('', 'http://evil.example.com', '../my-local', 'a'*300):
            with self.assertRaises(runner.TrialError):
                runner.LocalOllama(name)
    def test_duplicate_test_task(self):
        m, train, test = fixture()
        test[1]['task_id']='arith-test'
        with self.assertRaises(runner.TrialError):
            runner.build_requests(m, train, test)
    def test_no_train_test_overlap(self):
        m, train, test = fixture()
        m['train_task_ids'].append('arith-test')
        with self.assertRaisesRegex(runner.TrialError,'overlap'):
            runner.build_requests(m,train,test)
    def test_missing_test(self):
        m, train, test = fixture()
        with self.assertRaisesRegex(runner.TrialError,'missing test prompts'):
            runner.build_requests(m,train,test[:-1])
    def test_backend_failure_has_partial_receipt(self):
        m, train, test = fixture()
        with tempfile.TemporaryDirectory() as t:
            seen=[0]
            def backend(p):
                seen[0]+=1
                if seen[0]==3: raise RuntimeError('demo failure')
                return ('x', 1)
            output=Path(t)/'output'
            with self.assertRaises(RuntimeError):
                runner.run(runner.build_requests(m,train,test),m['model_id'],backend,output)
            self.assertEqual(len((output/'attempts.jsonl').read_text().splitlines()),2)

if __name__ == '__main__': unittest.main()
