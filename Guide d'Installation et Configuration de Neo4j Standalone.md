# Guide d'Installation et Configuration de Neo4j Standalone

## 1. Prérequis (Déjà Installés)

- Java 17 OpenJDK installé et fonctionnel
- Droits sudo disponibles
- Espace disque suffisant (au moins 2 Go recommandés)

## 2. Installation de Neo4j via le Dépôt Officiel

### 2.1 Ajout du Dépôt Neo4j

```bash
# Installer les dépendances nécessaires
sudo apt-get install -y wget apt-transport-https software-properties-common

# Ajouter la clé GPG de Neo4j
wget -O - https://debian.neo4j.com/neotechnology.gpg.key | sudo apt-key add -

# Ajouter le dépôt Neo4j
echo 'deb https://debian.neo4j.com stable latest' | sudo tee -a /etc/apt/sources.list.d/neo4j.list

# Mettre à jour les dépôts
sudo apt-get update
```

### 2.2 Installation du Package Neo4j

```bash
# Installer Neo4j Community Edition
sudo apt-get install -y neo4j

# Vérifier l'installation
neo4j --version
```

## 3. Configuration de Base de Neo4j

### 3.1 Fichier de Configuration Principal

Le fichier de configuration principal se trouve à `/etc/neo4j/neo4j.conf`. Voici les modifications recommandées :

```bash
# Éditer le fichier de configuration
sudo nano /etc/neo4j/neo4j.conf
```

Modifications à apporter :

1. **Activer l'accès distant** (décommenter et modifier) :
   ```
   dbms.default_listen_address=0.0.0.0
   ```

2. **Configurer l'authentification** (décommenter) :
   ```
   dbms.security.auth_enabled=true
   ```

3. **Activer les procédures APOC** (ajouter à la fin du fichier) :
   ```
   dbms.security.procedures.unrestricted=apoc.*
   ```

### 3.2 Installation du Plugin APOC

Pour les relations dynamiques, le plugin APOC est nécessaire :

```bash
# Créer le répertoire plugins s'il n'existe pas
sudo mkdir -p /var/lib/neo4j/plugins

# Télécharger le plugin APOC compatible avec votre version de Neo4j
sudo wget -P /var/lib/neo4j/plugins https://github.com/neo4j/apoc/releases/download/5.13.0/apoc-5.13.0-core.jar

# Définir les permissions correctes
sudo chown -R neo4j:neo4j /var/lib/neo4j/plugins
```

## 4. Gestion du Service Neo4j

### 4.1 Démarrage et Activation du Service

```bash
# Démarrer le service Neo4j
sudo systemctl start neo4j

# Activer le démarrage automatique au boot
sudo systemctl enable neo4j

# Vérifier le statut du service
sudo systemctl status neo4j
```

### 4.2 Vérification des Ports

Neo4j utilise plusieurs ports :
- 7474 : Interface HTTP (Neo4j Browser)
- 7473 : Interface HTTPS
- 7687 : Protocole Bolt (utilisé par les drivers)

Vérifiez que ces ports sont ouverts et en écoute :

```bash
sudo netstat -tulpn | grep -E '7474|7687'
```

## 5. Configuration du Mot de Passe Initial

Par défaut, Neo4j utilise le nom d'utilisateur `neo4j` avec le mot de passe `neo4j` à la première connexion. Vous devrez le changer lors de la première utilisation :

```bash
# Connexion à Neo4j via cypher-shell
cypher-shell -u neo4j -p neo4j

# Si demandé, définir un nouveau mot de passe
# Exemple : "synergesis_password"
```

Alternativement, vous pouvez définir le mot de passe via la ligne de commande :

```bash
neo4j-admin set-initial-password synergesis_password
```

## 6. Accès à Neo4j Browser

Neo4j Browser est une interface web pour interagir avec la base de données :

```
http://localhost:7474
```

Identifiants de connexion :
- Utilisateur : `neo4j`
- Mot de passe : celui défini à l'étape 5

## 7. Configuration pour l'Intégration avec Synergesis

### 7.1 Installation du Driver Python Neo4j

```bash
pip install neo4j
```

### 7.2 Configuration du Module d'Export

Modifiez le fichier de configuration ou les variables d'environnement pour l'intégration :

```bash
# Variables d'environnement
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="synergesis_password"
```

Ou directement dans le code :

```python
exporter = Neo4jExporter(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="synergesis_password",
    use_apoc_rels=True  # Si APOC est installé
)
```

## 8. Vérification de l'Installation

### 8.1 Test de Connexion via Python

Créez un script Python pour tester la connexion :

```python
from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
user = "neo4j"
password = "synergesis_password"

try:
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        with driver.session() as session:
            result = session.run("RETURN 'Connection successful' AS message")
            print(result.single()["message"])
    print("Neo4j connection test passed!")
except Exception as e:
    print(f"Neo4j connection test failed: {e}")
```

### 8.2 Vérification des Contraintes et Indexes

Exécutez les requêtes suivantes dans Neo4j Browser pour vérifier que les contraintes peuvent être créées :

```cypher
CREATE CONSTRAINT glyph_id_unique IF NOT EXISTS
FOR (g:Glyph) REQUIRE g.id IS UNIQUE;

CREATE INDEX glyph_concept_type IF NOT EXISTS
FOR (g:Glyph) ON (g.concept_type);

SHOW CONSTRAINTS;
SHOW INDEXES;
```

## 9. Dépannage

### 9.1 Problèmes de Démarrage du Service

Si le service ne démarre pas :

```bash
# Vérifier les logs
sudo journalctl -u neo4j -f

# Vérifier les permissions
sudo chown -R neo4j:neo4j /var/lib/neo4j/
```

### 9.2 Problèmes de Connexion

Si vous ne pouvez pas vous connecter :

```bash
# Vérifier que le service est en cours d'exécution
sudo systemctl status neo4j

# Vérifier les ports en écoute
sudo netstat -tulpn | grep -E '7474|7687'

# Vérifier les logs pour les erreurs d'authentification
sudo cat /var/log/neo4j/neo4j.log | grep -i auth
```

### 9.3 Réinitialisation du Mot de Passe

Si vous avez oublié le mot de passe :

```bash
# Arrêter le service
sudo systemctl stop neo4j

# Réinitialiser le mot de passe
sudo neo4j-admin set-initial-password nouveau_mot_de_passe

# Redémarrer le service
sudo systemctl start neo4j
```

## 10. Sauvegarde et Restauration

### 10.1 Sauvegarde de la Base de Données

```bash
# Arrêter le service
sudo systemctl stop neo4j

# Créer une sauvegarde
sudo neo4j-admin dump --database=neo4j --to=/path/to/backup/neo4j-backup.dump

# Redémarrer le service
sudo systemctl start neo4j
```

### 10.2 Restauration de la Base de Données

```bash
# Arrêter le service
sudo systemctl stop neo4j

# Restaurer depuis une sauvegarde
sudo neo4j-admin load --database=neo4j --from=/path/to/backup/neo4j-backup.dump --force

# Redémarrer le service
sudo systemctl start neo4j
```

---

*Guide généré le 30 mai 2025*
