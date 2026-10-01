"""Run an evidence-handling comparison; demo mode is a scripted control only."""
import argparse
from pathlib import Path

from synergesis_benchmark import DemoBackend, run_comparison
from synergesis_ollama_backend import OllamaBackend


def main(argv=None):
    parser = argparse.ArgumentParser(description="Comparer le même modèle avec et sans contexte Syn")
    parser.add_argument("--provider", choices=["demo", "ollama"], default="demo")
    parser.add_argument("--model", help="Nom exact du modèle déjà installé dans Ollama")
    parser.add_argument("--output", type=Path, required=True, help="Nouveau dossier de résultats")
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--port", type=int, default=11434)
    args = parser.parse_args(argv)
    if args.provider == "ollama" and not args.model:
        parser.error("--model est requis pour Ollama")
    if args.provider == "demo" and (args.model or args.port != 11434):
        parser.error("--model et --port concernent Ollama uniquement")
    try:
        if args.provider == "demo":
            factory = DemoBackend
            identity = {"provider": "scripted_control", "model": None, "scripted_demo": True}
        else:
            # Validate before creating artifacts or contacting a provider.
            OllamaBackend(args.model, port=args.port, seed=args.seed)
            factory = lambda: OllamaBackend(args.model, port=args.port, seed=args.seed)
            identity = {"provider": "ollama_loopback", "model": args.model,
                        "port": args.port, "temperature": 0, "seed": args.seed,
                        "num_predict": 512, "format": "json", "scripted_demo": False}
        report = run_comparison(args.output, factory, identity, seed=args.seed, repeats=args.repeats)
    except (ValueError, OSError):
        parser.exit(2, "Impossible de lancer : paramètres invalides ou dossier déjà existant/inaccessible.\n")
    print("CONTRÔLE SIMULÉ : ne mesure pas les capacités d’un LLM." if args.provider == "demo"
          else "ESSAI DU MODÈLE LOCAL : résultats limités aux tâches synthétiques de mémoire et de documents.")
    for arm, summary in report["summary"].items():
        print(f'{arm}: {summary["success_count"]}/{summary["cases"]} réponses et sources exactes, '
              f'{summary["failed"]} échecs techniques, {summary["parse_failure_count"]} JSON invalides, '
              f'{summary["wall_seconds"]:.3f} s')
    print(f'Rapport : {args.output.absolute() / "report.json"}')
    return 1 if any(s["failed"] or s["skipped"] for s in report["summary"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
