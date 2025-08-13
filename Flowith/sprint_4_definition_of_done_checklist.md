# Sprint 4 - Definition of Done

> Cette checklist représente notre contrat de qualité partagé. Une tâche (User Story, bug, etc.) est considérée comme **"Terminée" (Done)** uniquement si tous les points applicables ci-dessous sont validés.

---

### 1. Qualité du Code
- [ ] **Standards de nommage** : Les conventions de nommage du projet sont respectées pour les variables, fonctions, classes et fichiers.
- [ ] **Clarté et Commentaires** : Le code est clair et lisible. La logique complexe ou les décisions non évidentes sont expliquées par des commentaires concis.
- [ ] **Principe DRY** : Le principe *Don't Repeat Yourself* est appliqué. Il n'y a pas de duplication de code inutile ; la logique réutilisable est abstraite dans des fonctions ou des classes.
- [ ] **Style de Code** : Le code est conforme au guide de style (linter) du projet et ne génère aucune erreur de formatage.

### 2. Tests
- [ ] **Couverture des Tests Unitaires** : La couverture de code par les tests unitaires pour les nouvelles fonctionnalités ou modifications atteint ou dépasse **90%**.
- [ ] **Tests d'Intégration** : Tous les tests d'intégration pertinents pour la fonctionnalité développée passent avec succès.
- [ ] **Intégration au Pipeline** : Les nouveaux tests (unitaires et intégration) sont correctement ajoutés et configurés pour s'exécuter dans le pipeline de CI.

### 3. Revue de Code (Pull Request)
- [ ] **Approbation Requise** : La Pull Request (PR) a reçu au moins **une approbation** d'un autre membre de l'équipe.
- [ ] **Résolution des Commentaires** : Tous les commentaires et discussions soulevés durant la revue de code ont été traités et résolus.
- [ ] **Lien avec l'Issue** : La PR est explicitement liée à l'issue (ticket Jira, GitHub Issue, etc.) correspondante pour assurer la traçabilité.

### 4. Documentation
- [ ] **Documentation Interne** : La documentation interne au code (par exemple, docstrings en Python, JSDoc en JavaScript, commentaires de bloc) est présente, à jour et décrit l'objectif, les paramètres et les retours des fonctions/méthodes publiques.
- [ ] **Documentation Externe** : Si les changements impactent l'architecture, l'utilisation d'une API ou les processus de déploiement, la documentation externe correspondante (ex: Confluence, `README.md`, Postman Collection) a été mise à jour.

### 5. Intégration Continue (CI)
- [ ] **Build CI Valide** : Le build du pipeline d'intégration continue (CI) associé à la branche de la PR passe avec succès. Cela inclut toutes les étapes critiques : compilation, analyse statique (linting) et exécution de la suite de tests complète.

### 6. Fonctionnalité
- [ ] **Critères d'Acceptation** : La fonctionnalité implémentée répond à **tous** les critères d'acceptation définis dans la user story ou la description de la tâche.
- [ ] **Validation Manuelle (si applicable)** : La fonctionnalité a été testée manuellement par le développeur ou un testeur dans un environnement de développement/staging pour s'assurer qu'elle se comporte comme attendu du point de vue de l'utilisateur.