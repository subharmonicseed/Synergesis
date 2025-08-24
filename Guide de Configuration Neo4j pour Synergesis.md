# Guide de Configuration Neo4j pour Synergesis

## 1. Limitations de l'Environnement Actuel

Après vérification, l'environnement actuel présente les limitations suivantes :
- Docker n'est pas disponible (`docker: command not found`)
- Installation de logiciels système limitée (droits administrateur requis)

Ces limitations nous empêchent d'installer Neo4j localement via Docker ou en mode standalone, ce qui était notre approche privilégiée.

## 2. Alternatives pour l'Intégration Neo4j

### 2.1 Option A : Neo4j AuraDB (Service Cloud)

Neo4j propose un service cloud appelé AuraDB qui offre une instance Neo4j entièrement gérée :

1. **Avantages** :
   - Aucune installation locale requise
   - Interface Neo4j Browser accessible via navigateur web
   - Support natif d'APOC (plugin pour relations dynamiques)
   - Sauvegarde automatique et haute disponibilité

2. **Étapes de configuration** :
   - Créer un compte sur [Neo4j Aura](https://neo4j.com/cloud/platform/aura-graph-database/)
   - Choisir l'option gratuite "AuraDB Free" (limité mais suffisant pour les tests)
   - Créer une instance et noter les informations de connexion :
     - URI (généralement `neo4j+s://xxxxx.databases.neo4j.io`)
     - Nom d'utilisateur (généralement `neo4j`)
     - Mot de passe (généré lors de la création)

3. **Configuration du module d'export** :
   ```python
   exporter = Neo4jExporter(
       uri="neo4j+s://xxxxx.databases.neo4j.io",
       user="neo4j",
       password="votre_mot_de_passe",
       use_apoc_rels=True
   )
   ```

### 2.2 Option B : Instance Neo4j Distante

Si vous disposez déjà d'une instance Neo4j dans votre infrastructure :

1. **Prérequis** :
   - Instance Neo4j accessible via réseau
   - Port 7687 ouvert pour les connexions Bolt
   - Identifiants de connexion valides

2. **Configuration du module d'export** :
   ```python
   exporter = Neo4jExporter(
       uri="bolt://adresse_serveur:7687",
       user="neo4j",
       password="votre_mot_de_passe",
       use_apoc_rels=True
   )
   ```

3. **Vérification APOC** :
   - Confirmer que le plugin APOC est installé si l'approche avec relations dynamiques est choisie
   - Sinon, utiliser `use_apoc_rels=False` pour l'approche générique

### 2.3 Option C : Simulation d'Export (Solution de Contournement)

En l'absence d'accès à une instance Neo4j, nous pouvons simuler l'export :

1. **Génération de scripts Cypher** :
   - Utiliser la méthode `generate_cypher_for_glyphs()` pour générer les scripts Cypher
   - Sauvegarder ces scripts pour exécution ultérieure

2. **Documentation détaillée** :
   - Fournir des instructions précises pour l'exécution des scripts
   - Documenter les requêtes de validation à exécuter après import

## 3. Recommandation

Compte tenu des limitations actuelles, nous recommandons l'**Option A : Neo4j AuraDB** pour les raisons suivantes :
- Aucune installation locale requise
- Configuration rapide (moins de 5 minutes)
- Interface Neo4j Browser accessible depuis n'importe quel navigateur
- Support natif d'APOC pour les relations dynamiques
- Option gratuite suffisante pour les tests initiaux

## 4. Étapes Suivantes

1. **Choix de l'option** :
   - Confirmer votre préférence parmi les options proposées

2. **Configuration** :
   - Suivre les étapes de configuration correspondant à l'option choisie

3. **Test d'export** :
   - Exécuter le pipeline d'export sur les glyphes du golden set
   - Valider les résultats dans Neo4j Browser

4. **Documentation** :
   - Produire un rapport détaillé des résultats
   - Fournir des captures d'écran et requêtes de validation

## 5. Check-list de Vérification

Avant de procéder à l'export, vérifier :
- [ ] Instance Neo4j accessible (test de connexion réussi)
- [ ] Driver Neo4j Python installé (`pip install neo4j`)
- [ ] Variables d'environnement ou paramètres de connexion configurés
- [ ] Glyphes du golden set disponibles et validés
- [ ] Plugin APOC disponible (si approche avec relations dynamiques)
