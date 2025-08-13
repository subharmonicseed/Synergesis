> **Statut : Planification terminée – Exécution démarrée**

# Sprint 4 Task Tracker

| | |
| :--- | :--- |
| **Document ID:** | S4-KICKOFF-20250718-FINAL |
| **Sprint Cycle:** | Sprint 4 |
| **État:** | **Verrouillé – Suivi de l'exécution** |
| **Date:** | 18 juillet 2025 |

---

### **Artefacts de référence**

Cette planification de sprint est basée sur les documents stratégiques suivants qui constituent la source unique de vérité pour l'architecture et les objectifs.

*   **Spécification Architecturale Définitive**
    *   *Description :* Le document faisant autorité qui décrit le modèle architectural du framework Synergesis, y compris le Blackboard, la boucle MAPE-K, la constellation d'agents et les contrats de données.
    *   *Lien :* `synergesis multiagent framework architecture specification.md`

*   **Document de Kick-off du Sprint 4 (Plan Original)**
    *   *Description :* La version initiale et complète du plan de sprint, qui a servi de base à cette version de suivi de l'exécution.
    *   *Lien :* `sprint 4 synergesis starter kit development plan.md`

*   **Hub du Projet SYNLGLYPH**
    *   *Description :* Le portail centralisé fournissant une vue d'ensemble du projet, les revues des sprints précédents, la feuille de route et les archives.
    *   *Lien :* `SYNLGLYPH Project Hub/index.html`

---

### **1. Directive du Sprint : Forger le Synergesis Starter Kit**

L'objectif unique de ce sprint est de **construire la première tranche verticale fonctionnelle de l'écosystème Synergesis**, tel que défini dans la Spécification Architecturale Définitive. Ce "Starter Kit" servira de preuve de concept fondamentale, validant nos modèles architecturaux de base : le modèle Blackboard (`World State DB`) et la boucle de contrôle MAPE-K (`Synergy Core`).

Le succès est défini par l'exécution réussie d'une tâche de bout en bout : d'un objectif déclaré dans un `Metascript`, orchestré par le `Synergy Core`, à l'analyse effectuée par notre premier agent de référence, `NOUS`.

### **2. Épopées et Objectifs du Sprint**

Ce sprint est organisé en quatre épopées principales, correspondant directement aux composants du Synergesis Starter Kit.

| Épopée | Groupe de Fonctionnalités | Objectif Principal |
| :--- | :--- | :--- |
| **SYN-201** | **Noyau du Framework** | Construire le système nerveux central : l'orchestrateur, la base de connaissances et l'analyseur de langage. |
| **SYN-202** | **Contrats d'Agent et Logique** | Établir l'interface d'agent universelle et créer la première bibliothèque d'analyse réutilisable. |
| **SYN-203** | **Agent de Référence : NOUS** | Développer et conteneuriser le premier agent spécialisé, prouvant le contrat d'agent. |
| **SYN-204** | **Validation de Bout en Bout** | Prouver que l'ensemble du système fonctionne de concert en exécutant et en vérifiant une tâche en direct. |

---

### **3. Répartition Détaillée des Tâches**

### **Épopée SYN-201 : Implémentation du Noyau du Framework**
**Objectif :** Construire l'infrastructure non-agent requise pour que le système fonctionne : la base de données, l'analyseur de langage et l'orchestrateur.

#### **Tâche 1.1 : Provisionner et Configurer la World State DB**
*   **User Story :** En tant qu'ingénieur de plateforme, je dois déployer et configurer un magasin clé-valeur prêt pour la production, afin qu'il puisse servir de "Blackboard" central pour toute la communication des agents.
*   **Critères d'Acceptation :**
    *   [ ] Une instance Redis (ou équivalent) est provisionnée et accessible à l'environnement de développement.
    *   [ ] Les détails de connexion (hôte, port, identifiants) sont stockés de manière sécurisée dans un service de configuration (ex: HashiCorp Vault, AWS Secrets Manager).
    *   [ ] Des contrôles de santé de base pour la base de données sont établis.
*   **Effort :** `3 Points de Story`

#### **Tâche 1.2 : Implémenter le Moteur Metascript (MVP)**
*   **User Story :** En tant que développeur de framework, j'ai besoin d'un analyseur de base pour le langage `.ms`, afin que le Synergy Core puisse comprendre les objectifs de haut niveau et les traduire en tâches initiales.
*   **Critères d'Acceptation :**
    *   [ ] Un nouveau module Python, `synergesis.metascript`, est créé.
    *   [ ] L'analyseur peut lire un fichier `.ms` et extraire le `goal`, `agent_capability_required`, et `input_data_key`.
    *   [ ] L'analyseur retourne un objet structuré représentant le script analysé, prêt à être consommé par le Synergy Core.
    *   [ ] L'analyseur gère gracieusement les erreurs de syntaxe dans le fichier d'entrée.
*   **Effort :** `5 Points de Story`

#### **Tâche 1.3 : Développer l'Orchestrateur Synergy Core (MVP)**
*   **User Story :** En tant que développeur de framework, j'ai besoin d'une boucle d'orchestration de base, afin que le système puisse surveiller la World State DB, planifier les prochaines étapes et exécuter des tâches en les distribuant aux agents.
*   **Critères d'Acceptation :**
    *   [ ] Le `Synergy Core` s'exécute comme un processus persistant.
    *   [ ] Il surveille une file d'attente spécifique ou un modèle de clé dans la World State DB pour les nouvelles soumissions de `Metascript`.
    *   [ ] Lors de la détection d'un nouveau script, il utilise le `Moteur Metascript` pour l'analyser.
    *   [ ] Il construit un objet `TaskPayload` valide basé sur le script analysé.
    *   [ ] Il distribue le `TaskPayload` en le plaçant sur une file d'attente de tâches désignée dans la World State DB (ex: `tasks:pending:{agent_type}`).
*   **Effort :** `8 Points de Story`

---

### **Épopée SYN-202 : Contrat d'Agent et Logique Réutilisable**
**Objectif :** Créer les actifs fondamentaux et réutilisables pour tout développement d'agent : l'interface `IAgent` et la bibliothèque d'analyse `syn-engine`.

#### **Tâche 2.1 : Définir l'Interface `IAgent` et les Contrats de Données (✓ Terminé)**
*   **User Story :** En tant que développeur de framework, je dois définir l'interface fondamentale `IAgent` et ses contrats de données associés (`TaskPayload`, `TaskResult`), afin que le Synergy Core puisse gérer de manière prévisible n'importe quel agent et assurer une communication typée et sûre.
*   **Critères d'Acceptation :**
    *   [x] Une classe de base abstraite `IAgent` est créée dans `synergesis.core.contracts`.
    *   [x] Elle définit les méthodes abstraites : `initialize(config: dict)`, `execute_task(task_payload: TaskPayload)`, et `shutdown()`.
    *   [x] Les modèles Pydantic `TaskPayload` et `TaskResult` sont définis conformément à la spécification architecturale.
    *   [x] Des docstrings complètes expliquent le but, les paramètres et le comportement attendu de l'interface et des modèles.
*   **Effort :** `3 Points de Story`

#### **Tâche 2.2 : Refactoriser la logique 'Syn' en bibliothèque `syn-engine` (✓ Terminé)**
*   **User Story :** En tant que développeur, je dois extraire les algorithmes d'analyse sémantique de l'application 'Syn' héritée dans un package Python autonome, afin qu'il puisse être versionné indépendamment et utilisé comme dépendance par l'agent `NOUS`.
*   **Critères d'Acceptation :**
    *   [x] Un nouveau dépôt Git `syn-engine` est créé.
    *   [x] Tout le code purement analytique est déplacé du backend 'Syn' vers la nouvelle structure de projet.
    *   [x] Le code `syn-engine` n'a **aucune** dépendance envers Flask ou tout autre composant spécifique au web.
    *   [x] Un fichier `pyproject.toml` est configuré, définissant les métadonnées et les dépendances.
*   **Effort :** `5 Points de Story`

#### **Tâche 2.3 : Publier `syn-engine` dans le Registre Interne**
*   **User Story :** En tant que développeur, je dois publier la version `0.1.0` de `syn-engine` dans notre Artifactory interne, afin qu'elle puisse être installée comme une dépendance standard dans l'environnement de l'agent `NOUS`.
*   **Critères d'Acceptation :**
    *   [ ] L'API publique de la bibliothèque est clairement définie via `__init__.py`.
    *   [ ] Un job de pipeline CI/CD est créé pour construire et publier le package.
    *   [ ] Un développeur peut exécuter avec succès `pip install syn-engine==0.1.0` depuis le registre interne.
*   **Effort :** `3 Points de Story`

---

### **Épopée SYN-203 : Implémentation de l'Agent de Référence (NOUS)**
**Objectif :** Construire, conteneuriser et déployer notre premier agent fonctionnel, `NOUS`, comme implémentation de référence pour tous les futurs agents.

#### **Tâche 3.1 : Implémenter le Squelette de l'Agent `NOUS`**
*   **User Story :** En tant que développeur d'agent, je dois créer une classe `NousAgent` qui implémente correctement l'interface `IAgent`, afin qu'elle se conforme au contrat du framework.
*   **Critères d'Acceptation :**
    *   [ ] Un nouveau répertoire `synergesis/agents/nous/` est créé.
    *   [ ] La classe `NousAgent` est définie, héritant de `IAgent`.
    *   [ ] Toutes les méthodes requises (`initialize`, `execute_task`, `shutdown`) sont implémentées avec du logging et une logique de remplacement.
    *   [ ] Le `requirements.txt` de l'agent liste `syn-engine==0.1.0`.
*   **Effort :** `3 Points de Story`

#### **Tâche 3.2 : Intégrer `syn-engine` dans `NOUS`**
*   **User Story :** En tant que développeur d'agent, je dois appeler la bibliothèque `syn-engine` depuis la méthode `execute_task`, afin que l'agent puisse exécuter sa fonction d'analyse sémantique spécialisée.
*   **Critères d'Acceptation :**
    *   [ ] La méthode `execute_task` déballe correctement le `TaskPayload`.
    *   [ ] L'agent lit ses données d'entrée depuis la World State DB en utilisant la clé fournie dans le payload.
    *   [ ] La méthode invoque les fonctions d'analyse de la bibliothèque `syn-engine` importée.
    *   [ ] Les résultats de l'analyse sont empaquetés dans un objet `TaskResult` et réécrits dans la World State DB à une clé comme `results:{task_id}`.
    *   [ ] L'agent gère gracieusement les erreurs d'analyse, en retournant un `TaskResult` avec un statut 'FAILURE'.
*   **Effort :** `5 Points de Story`

#### **Tâche 3.3 : Conteneuriser l'Agent `NOUS`**
*   **User Story :** En tant qu'ingénieur de plateforme, j'ai besoin d'une image Docker pour l'agent `NOUS`, afin qu'il puisse être déployé comme un processus isolé et scalable géré par le framework.
*   **Critères d'Acceptation :**
    *   [ ] Un `Dockerfile` est présent dans le répertoire `synergesis/agents/nous/`.
    *   [ ] Le processus de construction Docker installe correctement toutes les dépendances, y compris `syn-engine` depuis le registre interne.
    *   [ ] L'`ENTRYPOINT` du conteneur est un script qui initialise et exécute le processus de l'agent, le faisant écouter les tâches sur la World State DB.
    *   [ ] L'image est construite et poussée vers le registre de conteneurs en tant que `nous-agent:0.1.0`.
*   **Effort :** `3 Points de Story`

---

### **Épopée SYN-204 : Validation de Bout en Bout**
**Objectif :** Prouver l'intégration complète de tous les composants du Starter Kit en orchestrant un test du début à la fin. C'est la "Définition du Fini" ultime pour le Sprint 4.

#### **Tâche 4.1 : Rédiger le `Metascript` de Test (✓ Terminé)**
*   **User Story :** En tant qu'ingénieur QA, je dois écrire un simple fichier `Metascript`, afin de pouvoir définir de manière déclarative une tâche de test pour l'agent `NOUS`.
*   **Critères d'Acceptation :**
    *   [x] Un fichier est créé : `tests/e2e/metascripts/test_semantic_analysis.ms`.
    *   [x] Le script utilise une syntaxe valide pour définir un objectif, une capacité requise de `semantic-analysis`, et une clé de données d'entrée.
*   **Effort :** `2 Points de Story`

#### **Tâche 4.2 : Créer et Exécuter le Lanceur de Test E2E**
*   **User Story :** En tant qu'ingénieur QA, j'ai besoin d'un test automatisé qui exécute le script `test_semantic_analysis.ms` et vérifie le résultat, afin que nous puissions confirmer que toute la tranche verticale fonctionne.
*   **Critères d'Acceptation :**
    *   [ ] Une fonction de test `pytest` est créée dans `tests/e2e/test_starter_kit.py`.
    *   [ ] **Étape 1 :** Le script de test alimente la World State DB avec les données d'entrée nécessaires.
    *   [ ] **Étape 2 :** Le script de test place le contenu de `test_semantic_analysis.ms` sur la World State DB pour être récupéré par le `Synergy Core`.
    *   [ ] **Étape 3 :** Le test interroge la World State DB pour la clé de résultat attendue (ex: `results:{task_id}`).
    *   [ ] **Vérification :** Le test affirme que les données à la clé de résultat correspondent à la sortie attendue de `syn-engine`.
    *   [ ] **Logs Système :** Le test confirme via les logs ou l'état du système que la tâche a été traitée par `Synergy Core` et exécutée par un agent `NOUS`.
    *   [ ] Le test s'exécute proprement et passe dans l'environnement CI.
*   **Effort :** `5 Points de Story`