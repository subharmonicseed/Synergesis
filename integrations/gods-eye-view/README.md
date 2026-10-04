# Profil Syn pour le véritable God’s Eye View

Base vérifiée : `bilawalsidhu/gods-eye-view` au commit
`aa16b7c3b0166a89d8c7a6089e0aff53a22faaee`. Le dossier `overlay` contient seulement
les nouveaux fichiers du profil ; les sources upstream ne sont pas remplacées.
Copier `overlay/syn.html`, `overlay/vite.syn.config.js` et `overlay/src/syn/*`
aux mêmes emplacements relatifs dans une copie distincte de GEV à ce commit.
Conserver `LICENSE` et les attributions Cesium/USGS ; notice incluse ici.

Node supporté par cette base : ≥24.14 <25 ou ≥26 <27. Sur le PC, Node 24.21.0
portable a été obtenu sur nodejs.org et le ZIP Windows vérifié avec son SHASUMS :
`158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`.
Les dépendances viennent de `registry.npmjs.org`, selon `package-lock.json`.
Aucun script d’installation des packages n’est exécuté.

```bash
npm ci --ignore-scripts --no-audit --no-fund
node --test src/syn/model.test.mjs
node node_modules/vite/bin/vite.js build --config vite.syn.config.js --configLoader native
node node_modules/vite/bin/vite.js preview --config vite.syn.config.js --configLoader native
```

Ouvrir `http://127.0.0.1:5173/syn.html` quand Syn sert sa projection sur 127.0.0.1:8765.
Utiliser **preview**, pas le serveur de développement général de GEV : aucune route
MCP/provider ne doit être activée. Le profil n’expose que ses fichiers construits,
sans chargement de `.env`, publicDir ou serveur de providers.
Sur le PC, le serveur de développement a rencontré un accès refusé lors de son
scan de dépendances ; le build et le preview dédiés fonctionnent.

Les 12 tests vérifient les faits/géométries concordants, sources et preuves présentes,
les simulations explicitement distinctes, réponses affichables, états sans événements,
timeouts, redirects, plafond de six lectures et 1 Mio. Ils ne prouvent pas WebGL.
Le vrai rendu, la caméra et les événements USGS ont été contrôlés dans le navigateur
sur le PC en plus du build. La carte de base est volontairement peu détaillée :
texture NaturalEarthII locale, sans fond cartographique distant ni clé Cesium.
