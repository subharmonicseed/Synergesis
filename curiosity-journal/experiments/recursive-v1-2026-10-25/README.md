# Preuves exécutées : héritage récursif SYN v1

Deux études synthétiques exécutées avec le véritable Mistral local installé,
sur 12 puis 24 tâches réservées. Le code, les règles et le modèle sont identiques
entre études ; les données et graines de tâches sont nouvelles.

| Bras | Étude 1 | Réplication |
| --- | ---: | ---: |
| reset / SYN₀ | 4/12 | 7/24 |
| journal textuel | 4/12 | 5/24 |
| SYN₁ | 12/12 | 22/24 |
| SYN₂ | 12/12 | 24/24 |

Lire [le rapport et ses limites](../../../docs/SYN_RECURSIVE_RESULTS_2026-10-25.md)
et [l'architecture](../../../docs/SYN_RECURSIVE_INHERITANCE_V1.md).

- `study-summary.json` contient les résultats complets et les reçus de vérification.
- Les preuves détaillées ont été remises localement au fondateur : 439 fichiers
  de données synthétiques, graines, requêtes/réponses, états, décisions, registres,
  sources expérimentales et index SHA-256. Leur publication dans le dépôt public
  ne fait pas partie de cette proposition.

Avec l'archive locale extraite et les dépendances de cette branche sous Python POSIX/WSL :

```bash
python -m synergesis_recursive_audit syn-recursive-real-001
python -m synergesis_recursive_audit syn-recursive-real-002
```

Aucun appel de modèle n'est fait par ces commandes. Sous Windows natif, le mode
`--skip-ledgers` vérifie le contenu sans prétendre contrôler les registres POSIX.
Les empreintes permettent un audit de cohérence, sans certification indépendante
du transport, de l'horodatage ou de l'aveuglement de l'opérateur.
