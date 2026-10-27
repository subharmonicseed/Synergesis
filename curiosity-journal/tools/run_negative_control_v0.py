"""Reproduce the public toy ceiling-effect demonstration (NO AGENT/LLM)."""
import argparse
import importlib.util
import json
from pathlib import Path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fixture-seed', type=int, default=20261025)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    gen = module('gen', root / 'syn_holdout_pack_v0.py')
    runner = module('runner', root / 'syn_four_arm_trial_v0.py')
    scorer = module('scorer', root / 'syn_skill_transfer_eval_v0.py')
    smoke = module('smoke', root / 'smoke_rule_solver_v0.py')
    if args.out.exists():
        raise SystemExit('refusing to overwrite output')
    pack = args.out / 'pack'
    gen.build(pack, seed=args.fixture_seed, model_id='deterministic-independent-algorithm-v1')
    manifest = runner._read_json(pack / 'release/manifest.json')
    train = runner._read_jsonl(pack / 'release/train_examples.jsonl')
    test = runner._read_jsonl(pack / 'holdout/test_prompts.jsonl')
    # Important separation: solver sees only prompts, not the oracle.
    requests = runner.build_requests(manifest, train, test)
    trial = runner.run(requests, manifest['model_id'], smoke.answer, args.out / 'run')
    # Oracle is opened only after all the answers were frozen to disk.
    truth = runner._read_jsonl(pack / 'sealed/oracle.jsonl')
    attempt_rows = runner._read_jsonl(args.out / 'run/attempts.jsonl')
    score = scorer.evaluate(manifest, truth, attempt_rows)
    (args.out / 'score.json').write_text(json.dumps(score, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'model': 'NON-LLM DETERMINISTIC NEGATIVE CONTROL',
                      'n_attempts': trial['n_attempts'],
                      'scores': {arm: score['results_by_arm'][arm]['passed'] for arm in scorer.ARMS},
                      'n_tasks_per_arm': score['n_tasks'],
                      'regressions': len(score['regressed_tasks']),
                      'meaning': 'Only confirms code-path behavior and task ceiling; proves NOTHING about SYN or AGI.'}, indent=2))


if __name__ == '__main__':
    main()
