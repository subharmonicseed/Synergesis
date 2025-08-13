# Sprint 4 - Tableau d'Affectation des Tâches

**Objectif :** Ce document liste les tâches techniques à réaliser pour le Sprint 4. Il sert de base pour l'assignation des responsabilités au sein de l'équipe de développement.

| ID Tâche/User Story | Description Sommaire | Propriétaire (à assigner) |
| :--- | :--- | :--- |
| **Tâche 1.1** | En tant qu'ingénieur de plateforme, je dois déployer et configurer un magasin clé-valeur prêt pour la production, afin qu'il puisse servir de "Blackboard" central pour toute la communication des agents. | |
| **Tâche 1.2** | En tant que développeur de framework, j'ai besoin d'un analyseur de base pour le langage `.ms`, afin que le Synergy Core puisse comprendre les objectifs de haut niveau et les traduire en tâches initiales. | |
| **Tâche 1.3** | En tant que développeur de framework, j'ai besoin d'une boucle d'orchestration de base, afin que le système puisse surveiller la World State DB, planifier les prochaines étapes et exécuter des tâches en les distribuant aux agents. | |
| **Tâche 2.3** | En tant que développeur, je dois publier la version `0.1.0` de `syn-engine` dans notre Artifactory interne, afin qu'elle puisse être installée comme une dépendance standard dans l'environnement de l'agent `NOUS`. | |
| **Tâche 3.1** | En tant que développeur d'agent, je dois créer une classe `NousAgent` qui implémente correctement l'interface `IAgent`, afin qu'elle se conforme au contrat du framework. | |
| **Tâche 3.2** | En tant que développeur d'agent, je dois appeler la bibliothèque `syn-engine` depuis la méthode `execute_task`, afin que l'agent puisse exécuter sa fonction d'analyse sémantique spécialisée. | |
| **Tâche 3.3** | En tant qu'ingénieur de plateforme, j'ai besoin d'une image Docker pour l'agent `NOUS`, afin qu'il puisse être déployé comme un processus isolé et scalable géré par le framework. | |
| **Tâche 4.2** | En tant qu'ingénieur QA, j'ai besoin d'un test automatisé qui exécute le script `test_semantic_analysis.ms` et vérifie le résultat, afin que nous puissions confirmer que toute la tranche verticale fonctionne. | |