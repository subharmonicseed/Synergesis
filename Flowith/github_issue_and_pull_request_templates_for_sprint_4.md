# Modèles GitHub pour le Sprint 4

Ce document contient les modèles standards pour la création des Issues et des Pull Requests durant le Sprint 4.

---

## Modèle d'Issue (Bug / Feature)

```markdown
### [BUG / FEATURE] : Titre concis et descriptif

---

**Description**

*Fournissez ici une description claire et détaillée du bug ou de la fonctionnalité. Pour une feature, expliquez le besoin utilisateur et la valeur ajoutée. Pour un bug, décrivez l'impact sur l'utilisateur.*

---

**Étapes de reproduction (pour les bugs)**

*Décrivez précisément les étapes pour reproduire le bug. Si ce n'est pas un bug, vous pouvez supprimer cette section.*
1. Se rendre sur la page '...'
2. Cliquer sur le bouton '....'
3. Remplir le formulaire avec les données '...'
4. L'erreur suivante apparaît : ...

**Comportement attendu vs. Comportement actuel**
- **Attendu :** *Ce qui aurait dû se passer.*
- **Actuel :** *Ce qui se passe réellement.*

---

**Critères d'acceptation**

*Définissez les conditions qui doivent être remplies pour que la tâche soit considérée comme terminée. Utilisez des cases à cocher.*
- [ ] Le formulaire peut être soumis avec succès lorsque...
- [ ] Un message de confirmation est affiché à l'utilisateur.
- [ ] Les données sont correctement enregistrées en base de données.

---

**Labels**
- `S4`
- `bug` ou `feature`
- `priorité: haute/moyenne/basse`

```

---
---

## Modèle de Pull Request

```markdown
### feat/fix(scope): Titre concis et explicite du changement

---

**Description**

*Expliquez le **quoi** et le **pourquoi** de ces changements. Quelle est la logique derrière votre approche ? Quel problème cette PR résout-elle ? S'il y a des changements d'UI, ajoutez une capture d'écran.*

---

**Issues liées**

*Liez cette PR à l'issue correspondante pour assurer la traçabilité. Utilisez les mots-clés `Closes`, `Fixes` ou `Resolves` pour fermer l'issue automatiquement après le merge.*
- Closes #...

---

### Definition of Done (DoD) - Checklist du développeur

*Avant de soumettre votre PR pour revue, veuillez valider chaque point de cette checklist. Votre rigueur est la clé de notre qualité collective.*

- [ ] **Lien avec l'Issue** : La PR est correctement liée à son issue via la section "Issues liées".
- [ ] **Critères d'Acceptation** : Mon code répond à **tous** les critères d'acceptation définis dans l'issue.
- [ ] **Qualité du Code** : Le code respecte nos standards (nommage, clarté, principe DRY) et ne génère aucune alerte du linter.
- [ ] **Tests Unitaires** : La couverture de code par les tests unitaires pour les nouvelles fonctionnalités atteint ou dépasse **90%**.
- [ ] **Tests d'Intégration** : Tous les tests d'intégration pertinents pour la fonctionnalité passent avec succès.
- [ ] **Pipeline CI** : Le build du pipeline d'intégration continue (CI) associé à ma branche passe avec succès.
- [ ] **Documentation** : J'ai mis à jour la documentation nécessaire (commentaires de code, `README.md`, Confluence, etc.) si mes changements l'exigent.
- [ ] **Auto-revue** : J'ai relu mes propres changements (`git diff`) pour corriger les erreurs évidentes ou les typos.
```