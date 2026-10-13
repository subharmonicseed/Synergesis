# Superviseur local v0 — missions scientifiques bornées

Le superviseur ajoute une mission explicite à l’interface de Syn. L’utilisateur écrit un objectif et choisit une à trois requêtes arXiv différentes. Le service exécute ce plan fixe, conserve ses étapes et affiche ses résultats. Le modèle ne choisit ni les requêtes suivantes, ni les budgets, ni une action supplémentaire.

## Autorisation et parcours

Dans **Mission scientifique**, saisir un objectif de 1 à 2 048 caractères et une à trois requêtes, une par ligne, de 300 caractères maximum chacune. Les requêtes doivent être différentes et ne contenir aucun caractère de contrôle. Cocher l’autorisation puis cliquer sur **Lancer la mission autorisée**. `--internet` doit être actif et le modèle Ollama déjà installé doit être disponible.

L’autorisation est liée au modèle local exact, aux requêtes et à leur empreinte de portée. Le plan contient une recherche arXiv puis un examen local pour chaque requête. Au maximum trois recherches et trois appels Ollama sont réservés, avec un seul effet extérieur par passage du superviseur. Une recherche sans extrait laisse sa synthèse non effectuée. Les réservations consomment le budget avant l’appel : un échec ou une interruption ne rend pas cette réservation disponible.

Le service consulte les résumés arXiv ; il ne lit pas automatiquement les articles PDF et ne cherche pas sur tout Internet. Les requêtes choisies sont transmises à arXiv. Les extraits sont examinés par le fournisseur Ollama local, sans clé API, téléchargement de modèle ou service de modèle cloud.

Le panneau affiche l’objectif, l’état, les budgets restants, la dernière étape, la prochaine reprise, l’échéance, le motif d’un arrêt ou blocage, les résultats et les reçus. Une source consultée, une référence fournie au modèle et une citation repérée dans sa réponse ont des sens distincts. Leur affichage ne valide pas une conclusion scientifique.

## Propriété du moteur et exécution

`LocalUIService` garde son worker moteur unique. Ce worker ouvre et ferme les conversations, possède le profil, réserve et confirme les étapes et écrit les états, reçus et journaux. Les threads HTTP lisent des instantanés et déposent les demandes ; ils n’acquièrent pas le contexte moteur.

`synergesis_supervisor.Supervisor` est une machine d’état passive. Il ne démarre aucun thread, processus, modèle ou requête réseau. Le worker existant appelle `next_delay()` puis `tick()` lorsque la mission est éligible. Un passage produit au plus un effet extérieur. Entre deux étapes, une attente locale remplace tout appel au modèle.

Pendant un appel réseau de mission, un helper temporaire effectue uniquement l’entrée/sortie HTTP et rapporte ses octets ou son résultat au worker. Le worker attend sa terminaison et le joint avant de poursuivre. Pendant cette attente, il relève les contrôles environ toutes les 0,2 seconde et peut enregistrer durablement une pause ou un arrêt. Ce helper n’accède pas au contexte moteur, ne confirme pas une étape et n’écrit pas ses preuves. Il ne constitue pas un daemon ou un second moteur permanent.

`SynGoalManager(runtime=None)` est réutilisé pour enregistrer l’objectif et les événements de cycle de vie dans `goals.jsonl`. Le superviseur garde l’autorité sur les réservations et budgets. Aucun `SynPlannerRuntime` ou agent planificateur n’est lancé. `SynRoamService` a été examiné pour son motif de réservation et de reprise à partir des reçus ; il n’est pas lancé comme service de cette interface.

Les composants AEGIS, RISK et REALITY du parcours de conversation encadrent la remise `emit_reply` à la boîte locale de réponse. Dans ce raccordement, ils ne constituent pas une autorisation ou une vérification de l’appel HTTP arXiv/Ollama lui-même. Les contrôles de portée du superviseur précèdent ces appels. La confirmation REALITY atteste la remise du texte au programme, pas sa vérité, sa qualité ou la justesse de ses citations.

## Échéance, pause, arrêt et repos

L’échéance est persistée à la création : `created_at + 600` secondes. Avant d’engager un nouvel effet, le worker revérifie l’autorisation, les contrôles et cette échéance. Une pause, une reprise, une nouvelle conversation ou une relance du service ne prolonge pas ces dix minutes et ne réinitialise pas les budgets de mission.

Les adaptateurs réduisent leurs délais coopératifs selon le temps restant. Le délai socket Ollama est plafonné à 180 secondes ; arXiv dispose de délais plus courts. Ces valeurs concernent l’attente réseau et l’inactivité du socket : elles ne garantissent pas l’interruption absolue d’un appel à 180 secondes, ni la terminaison du processus à dix minutes. Un appel déjà engagé peut encore se terminer après l’échéance. Son résultat connu est conservé, sans engager le suivant.

**Mettre en pause** ou **Arrêter la mission** envoie un contrôle même si le worker attend un appel de mission. Le HTTP `202` signifie réception, pas encore persistance du contrôle. Le panneau montre la demande en attente jusqu’à l’état confirmé par le worker. Une fois enregistrée, la pause ou l’arrêt empêche les appels suivants ; le résultat d’un appel déjà engagé peut néanmoins être conservé. La confirmation de ce résultat ne réactive pas une mission arrêtée ou en pause.

**Reprendre** est une action explicite pour une mission `paused` ou `suspended`, lorsque le worker est disponible. Elle conserve le budget et l’échéance. Une échéance passée bloque la reprise. Une mission `blocked` avec issue inconnue nécessite l’examen de ses traces ; elle n’est pas reprise automatiquement. Deux recherches consécutives sans preuve de contenu nouvelle ou deux échecs connus consécutifs peuvent suspendre le plan.

Sans mission active, aucune inférence LLM n’est déclenchée par le superviseur. La vérification périodique de disponibilité utilise seulement `GET /api/tags` sur le fournisseur Ollama de bouclage, sans requête de conversation, sans profil transmis et sans `pull` de modèle. Fermer l’onglet ne coupe pas le service. Windows, WSL et le serveur doivent rester actifs : cette version ne réveille pas le PC et ne fonctionne pas après sa mise en veille ou son arrêt.

## Persistance, déduplication et reprise d’une interruption

Sous le dossier de service, `supervisor/current.json` pointe vers la mission courante. Chaque mission garde son `state.json`, ses réservations, ses preuves d’étape et son autorisation. Les fichiers sont remplacés atomiquement, avec empreinte de contenu et synchronisation disque. Les archives des missions précédentes restent sur disque ; l’interface v0 montre la mission courante.

L’identifiant stable d’étape relie la réservation au reçu de recherche ou au cycle de remise de synthèse. Le raccordement garde également les preuves locales sous `mission-effects/` et les conversations de synthèse sous `mission-conversations/`. Le profil conserve les reçus de recherche ; chaque synthèse utilise une conversation dédiée, limitée aux extraits du reçu de sa recherche.

Après une interruption, une réservation encore `reserved` est examinée sans appel réseau ni modèle. Une preuve locale correspondante peut confirmer le résultat déjà connu. La recherche doit avoir son reçu persistant associé à l’étape. La synthèse doit avoir un cycle de remise auditée, son observation de boîte locale, son texte et les identifiants correspondants. Des octets Ollama seuls dans `transport.jsonl` ne prouvent pas cette remise et ne suffisent pas à confirmer une synthèse.

En l’absence de preuve correspondante, ou si les preuves sont invalides ou ambiguës, l’issue reste inconnue et la mission est bloquée sans rejeu automatique. Une mission déjà arrêtée reste arrêtée et signale cette incertitude. Ce choix empêche de répéter aveuglément un appel qui a peut-être eu lieu ; il ne garantit pas une exécution « exactement une fois » chez un fournisseur extérieur. Aucun résultat absent n’est remplacé par une simulation.

Un état actif sans étape incertaine peut continuer après relance dans sa portée initialement autorisée, si l’échéance reste valide. Un état en pause ou suspendu conserve son attente de reprise explicite. Redémarrer le service conserve les réservations, les compteurs et l’échéance ; changer de conversation ne crée pas de nouveau budget de mission.

La demande de lancement possède aussi un registre durable `supervisor/start-requests.json`. Le même UUID et la même portée retrouvent la mission enregistrée au lieu d’en créer une nouvelle ; une portée différente pour cet UUID est refusée. Ce registre borné conserve au maximum 128 lancements. Les contrôles de pause/reprise/arrêt ont une déduplication HTTP en mémoire pendant le lancement du serveur et une transition de mission persistante. Ils n’ont pas une garantie générale de rejeu des UUID après redémarrage. L’interface ne renvoie automatiquement aucune mutation dont le résultat est incertain.

## Contrat HTTP local

Les protections existantes restent appliquées : adresse de bouclage, validation de `Host`/`Origin`, jeton aléatoire `X-Syn-Token`, JSON borné et rendu des contenus comme texte. Les liens externes sont limités aux hôtes HTTPS arXiv autorisés.

`GET /api/state` expose `supervisor.mission` (ou `null`) et `mission_control` (ou `null`). La mission contient notamment `mission_id`, `goal_id`, `title`, `queries`, `model`, `status`, `reason`, `deadline`, `next_wake`, `budget`, `steps` et `last_step`. Les dates de mission sont des secondes Unix. `mission_control` indique une réception en attente de confirmation ; `operation` fournit le résultat de la commande.

Les mutations passent par `POST /api/action` avec UUID `request_id` et le jeton propre au lancement. Exemples de forme, à utiliser avec des valeurs de l’instance réelle :

```json
{"request_id":"UUID","action":"mission_start","text":"Objectif choisi","queries":["requête arXiv choisie"],"authorized":true}
```

```json
{"request_id":"UUID","action":"mission_pause","mission_id":"IDENTIFIANT_DE_MISSION"}
```

Les mêmes champs servent à `mission_resume` et `mission_stop`. Un contrôle portant sur une autre mission est refusé. Pendant une mission active, les mutations ordinaires du dialogue et du profil sont refusées ; la consultation des instantanés reste possible. Il n’existe aucune API permettant au modèle d’ajouter une requête ou d’augmenter ces budgets.

## Lancement sur le PC de Gabriel

Le lanceur de cette version utilise les sources natives `/home/gabriel/Synergesis-AutonomySupervisor-final`, le Python existant `/home/gabriel/syn-ollama51-venv/bin/python`, le modèle installé `syn-mistral-import:latest`, le profil `/home/gabriel/synergesis-ollama51/profil-utilisateur` et le dossier de service `/home/gabriel/synergesis-ollama51/interface-locale`. Il conserve les fichiers et journaux existants. Le serveur reste sur `http://127.0.0.1:8765` et Ollama sur le port local `11434`.

Après installation des sources vérifiées, `scripts/open_syn.ps1` ouvre l’interface et réutilise uniquement une instance correspondant au profil, au modèle, au dossier et à l’empreinte du manifeste. Une autre instance sur le port n’est pas arrêtée automatiquement. Les journaux de démarrage sont séparés sous `outputs/SynSupervisorLogs`. Le raccourci **Ouvrir Syn** doit pointer vers ce lanceur une fois la version installée ; sa préparation et le remplacement de l’ancien raccourci font partie du déploiement PC, pas du superviseur.

Commande équivalente depuis les sources installées dans WSL :

```bash
/home/gabriel/syn-ollama51-venv/bin/python -m synergesis_ui \
  --profile /home/gabriel/synergesis-ollama51/profil-utilisateur \
  --root /home/gabriel/synergesis-ollama51/interface-locale \
  --model syn-mistral-import:latest --port 8765 --ollama-port 11434 --internet
```

Arrêter une mission conserve ses résultats et laisse le dialogue disponible lorsque l’appel engagé est terminé. **Arrêter l’application** ferme le serveur et ses conversations proprement ; Ollama reste disponible. Un appel engagé doit terminer avant la libération de ses verrous. Le profil et le dossier de service ne sont pas supprimés.

## Validation et limites des preuves

Les tests `test_syn_supervisor.py`, `test_syn_supervisor_ui.py`, `test_syn_ui_backend.py` et `test_syn_ui_security.py` utilisent des horloges, fournisseurs, interruptions ou réponses contrôlés pour vérifier les réservations, budgets, transitions, reprises et protections. Une horloge simulée ou une panne injectée sert à vérifier un comportement déterminé ; elle n’atteste pas une recherche arXiv réelle ou une réponse du Mistral installé.

Les [résultats de validation](VALIDATION_AUTONOMY_V0.md) distinguent ces tests des parcours PC avec le véritable modèle. Les sources effectivement consultées, contrôles pendant un appel, relances et journaux complets sont conservés localement dans `outputs/SYN_SUPERVISEUR_RESULTAT_PC.md` et `outputs/SynSupervisorProofs`.

Les principales limites sont la lenteur du modèle local, les erreurs possibles de synthèse ou de citation, l’accès aux résumés arXiv uniquement, l’absence de planification ouverte, le besoin d’un PC/service actif et l’impossibilité de déduire un résultat certain lorsque le processus a été interrompu sans preuve corrélée. La v0 rend le travail et ses limites observables ; elle ne prouve pas un gain de raisonnement du modèle.
