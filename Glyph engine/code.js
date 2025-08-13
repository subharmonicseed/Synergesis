// glyphEngine.js

document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const canvas = document.getElementById('glyphCanvas');
    const ctx = canvas.getContext('2d');
    const genAutoBtn = document.getElementById('genAutoBtn');
    // const genRuleBtn = document.getElementById('genRuleBtn'); // Placeholder
    const combineBtn = document.getElementById('combineBtn');
    const clearCanvasBtn = document.getElementById('clearCanvasBtn');
    const saveSelectedBtn = document.getElementById('saveSelectedBtn');
    const exportArchiveBtn = document.getElementById('exportArchiveBtn');
    const importFileLabel = document.querySelector('label[for="importFile"]');
    const importFileInput = document.getElementById('importFile');
    const analysisContent = document.getElementById('analysisContent');
    const compatibilityScoreDiv = document.getElementById('compatibilityScore');
    const searchArchiveInput = document.getElementById('searchArchiveInput');
    const archiveList = document.getElementById('archiveList');
    const clearArchiveBtn = document.getElementById('clearArchiveBtn');

    // --- Configuration ---
    const BASE_GLYPH_SIZE = 100; // Taille de la zone logique du glyphe
    const SHAPE_MAX_SIZE_FACTOR = 0.4; // Facteur taille max forme / taille glyphe
    const MIN_SHAPES = 2;
    const MAX_SHAPES = 6;
    const STROKE_COLOR = '#333333';
    const STROKE_WIDTH = 1.5;
    const SELECTION_STROKE_COLOR = 'rgba(255, 107, 107, 0.8)'; // Rouge semi-transparent
    const SELECTION_LINE_WIDTH = 2;
    const ARCHIVE_ITEM_GLYPH_SCALE = 0.3; // Echelle pour preview dans l'archive (si implémenté)

    // --- State ---
    let currentGlyphs = [];
    let selectedGlyphs = [];
    let glyphArchive = [];
    let selectedArchiveId = null; // Pour savoir quel item d'archive est sélectionné

    // --- Canvas Resizing ---
    function resizeCanvas() {
        const container = canvas.parentElement;
        const computedStyle = getComputedStyle(container);
        const width = container.clientWidth - parseFloat(computedStyle.paddingLeft) - parseFloat(computedStyle.paddingRight);
        // Calcul de la hauteur basée sur le padding-bottom (technique de l'aspect ratio)
        const ratio = parseFloat(getComputedStyle(canvas).paddingBottom) / 100;
        const height = width * ratio;

        // Ajuster la résolution interne du canvas
        // Utiliser devicePixelRatio pour une meilleure netteté sur écrans HiDPI
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.scale(dpr, dpr); // Mettre à l'échelle le contexte

        console.log(`Canvas resized: ${canvas.width}x${canvas.height} (Style: ${width}x${height}) DPR: ${dpr}`);
        // Redessiner après redimensionnement
        requestAnimationFrame(drawAllGlyphs);
    }

    // Initial resize and listen for window resize
    const resizeObserver = new ResizeObserver(entries => {
        // On utilise requestAnimationFrame pour éviter des resize/redraw trop fréquents
         window.requestAnimationFrame(() => {
            if (!entries || !entries.length) {
                return;
            }
            resizeCanvas();
        });
    });
    // Observer le parent du canvas pour détecter les changements de taille
    resizeObserver.observe(canvas.parentElement);
    // Initial call
    resizeCanvas();


    // --- Glyph Class ---
    class Glyph {
        constructor(x, y, id = null, shapes = null, properties = null) {
            this.id = id || generateUUID();
            this.x = x;
            this.y = y;
            this.shapes = shapes || this.generateShapes('auto'); // Génère auto par défaut
            this.properties = properties || this.calculateInitialProperties();
            this.isSelected = false;
            // Bounding box simple basée sur BASE_GLYPH_SIZE pour l'interaction
            this.boundingBox = {
                x: this.x - BASE_GLYPH_SIZE / 2,
                y: this.y - BASE_GLYPH_SIZE / 2,
                width: BASE_GLYPH_SIZE,
                height: BASE_GLYPH_SIZE
            };
        }

        generateShapes(mode = 'auto', rules = {}) {
            const shapes = [];
            const numShapes = randomInt(MIN_SHAPES, MAX_SHAPES);
            const availableShapeTypes = Object.keys(SHAPE_SYMBOL_MAP);

            for (let i = 0; i < numShapes; i++) {
                const type = randomChoice(availableShapeTypes);
                const shape = { type };
                const shapeSymbolData = SHAPE_SYMBOL_MAP[type];

                // Position relative au centre (x, y)
                shape.x = randomRange(-BASE_GLYPH_SIZE * 0.35, BASE_GLYPH_SIZE * 0.35);
                shape.y = randomRange(-BASE_GLYPH_SIZE * 0.35, BASE_GLYPH_SIZE * 0.35);
                const maxSize = BASE_GLYPH_SIZE * SHAPE_MAX_SIZE_FACTOR;
                const size = randomRange(maxSize * 0.2, maxSize);
                shape.angle = randomRange(0, Math.PI * 2); // Angle générique

                switch (type) {
                    case 'circle':
                        shape.radius = size / 2;
                        break;
                    case 'triangle':
                        shape.size = size; // Base du triangle équilatéral
                        break;
                    case 'line':
                        shape.length = size; // Longueur de la ligne
                        break;
                    case 'arc':
                        shape.radius = size / 2;
                        shape.startAngle = shape.angle;
                        shape.endAngle = shape.angle + randomRange(Math.PI * 0.3, Math.PI * 1.8);
                         break;
                    // Ajouter d'autres formes ici
                }

                // Attribuer des propriétés symboliques *potentielles* à la forme elle-même
                // Ces propriétés influenceront le calcul global du glyphe
                shape.symbolicHints = {
                    polarity: Array.isArray(shapeSymbolData.polarityBias) ? randomChoice(shapeSymbolData.polarityBias) : shapeSymbolData.polarityBias,
                    freqMod: shapeSymbolData.freqMod,
                    weightMod: shapeSymbolData.weightMod,
                    alignmentHint: randomChoice(shapeSymbolData.alignmentHint)
                };
                shapes.push(shape);
            }
            return shapes;
            // TODO: Implémenter la génération basée sur les règles (`mode === 'rules'`)
        }

        calculateInitialProperties() {
            // Calcule les propriétés globales du glyphe basées sur ses formes
            let totalWeight = 0;
            let weightedFreqSum = 0;
            let polarityVotes = { '+': 0, '-': 0, '0': 0 };
            let alignmentVotes = {};
            SYMBOLIC_PROPERTIES.ALIGNMENT.forEach(a => alignmentVotes[a] = 0);
            let associatedValues = new Set(); // Utiliser un Set pour éviter les doublons

            this.shapes.forEach(shape => {
                const hints = shape.symbolicHints;
                const baseWeight = hints.weightMod; // Utiliser weightMod comme poids de la forme

                totalWeight += baseWeight;
                weightedFreqSum += randomRange(...SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE) * hints.freqMod * baseWeight;

                polarityVotes[hints.polarity]++;

                if (alignmentVotes[hints.alignmentHint] !== undefined) {
                     alignmentVotes[hints.alignmentHint]++;
                }

                // Exemple : ajouter un tag basé sur la forme
                 associatedValues.add(`shape:${shape.type}`);
                 // Exemple : ajouter un tag basé sur l'alignement hint
                 associatedValues.add(`align:${hints.alignmentHint}`);
            });

             // Déterminer la polarité dominante
             let dominantPolarity = '0';
             if (polarityVotes['+'] > polarityVotes['-'] && polarityVotes['+'] >= polarityVotes['0']) dominantPolarity = '+';
             else if (polarityVotes['-'] > polarityVotes['+'] && polarityVotes['-'] >= polarityVotes['0']) dominantPolarity = '-';
             else if (polarityVotes['+'] === polarityVotes['-'] && polarityVotes['+'] > 0) dominantPolarity = '0'; // Équilibre

             // Déterminer l'alignement dominant
             let dominantAlignment = randomChoice(SYMBOLIC_PROPERTIES.ALIGNMENT); // Défaut aléatoire
             let maxVotes = 0;
             for (const align in alignmentVotes) {
                 if (alignmentVotes[align] > maxVotes) {
                     maxVotes = alignmentVotes[align];
                     dominantAlignment = align;
                 }
             }
             // En cas d'égalité, on pourrait choisir aléatoirement parmi les ex aequo ou avoir une règle spécifique

             const finalFrequency = totalWeight > 0 ? Math.round(weightedFreqSum / totalWeight) : randomInt(...SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE);
             const finalWeight = Math.round(totalWeight * (SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[1] / MAX_SHAPES)); // Normalisation simple

            return {
                polarity: dominantPolarity,
                frequency: Math.max(SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE[0], Math.min(SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE[1], finalFrequency)),
                weight: Math.max(SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[0], Math.min(SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[1], finalWeight)),
                alignment: dominantAlignment,
                values: Array.from(associatedValues) // Convertir Set en Array
            };
        }

        draw(context, isSelectedOverride = false) {
            context.save();
            // Se positionner au centre du glyphe pour le dessin
            context.translate(this.x, this.y);

            context.lineWidth = STROKE_WIDTH;
            context.strokeStyle = STROKE_COLOR;
            context.fillStyle = 'none'; // Style épuré

            // Dessiner chaque forme relative au centre (0,0)
            this.shapes.forEach(shape => {
                drawShape(context, shape); // Utilise la fonction externe
            });

            // Dessiner la boîte de sélection si nécessaire
            if (this.isSelected || isSelectedOverride) {
                context.lineWidth = SELECTION_LINE_WIDTH;
                context.strokeStyle = SELECTION_STROKE_COLOR;
                // Dessine un cercle englobant au lieu d'un carré pour l'esthétique
                context.beginPath();
                context.arc(0, 0, BASE_GLYPH_SIZE / 2 + 5, 0, Math.PI * 2); // Légèrement plus grand
                context.stroke();
            }

            context.restore();
        }

        // Vérifie si un point (px, py) est dans la zone de clic du glyphe
        contains(px, py) {
             // Utilise une distance circulaire depuis le centre pour la sélection
             const distSq = (px - this.x)**2 + (py - this.y)**2;
             const radiusSq = (BASE_GLYPH_SIZE / 2)**2;
             return distSq <= radiusSq;
        }
    }

    // --- Core Functions ---

    function drawAllGlyphs() {
        // Utiliser la taille réelle du contexte après scaling DPR
        const effectiveWidth = canvas.width / (window.devicePixelRatio || 1);
        const effectiveHeight = canvas.height / (window.devicePixelRatio || 1);

        ctx.clearRect(0, 0, effectiveWidth, effectiveHeight); // Effacer le canvas

        currentGlyphs.forEach(glyph => glyph.draw(ctx));

        // Optionnel : Redessiner les glyphes sélectionnés par-dessus pour accentuer la sélection
        selectedGlyphs.forEach(glyph => {
            // glyph.draw(ctx, true); // Passer true pour forcer le dessin de sélection
            // -> Le dessin de sélection est déjà géré dans glyph.draw via this.isSelected
        });
    }

    function findGlyphAt(x, y) {
        // Trouve le glyphe le plus au premier plan (dernier dessiné) sous le clic
        for (let i = currentGlyphs.length - 1; i >= 0; i--) {
            if (currentGlyphs[i].contains(x, y)) {
                return currentGlyphs[i];
            }
        }
        return null;
    }

    function handleCanvasClick(event) {
        const { x, y } = getCanvasMousePos(canvas, event);
        const clickedGlyph = findGlyphAt(x, y);

        if (clickedGlyph) {
            if (selectedGlyphs.includes(clickedGlyph)) {
                // Désélectionner
                clickedGlyph.isSelected = false;
                selectedGlyphs = selectedGlyphs.filter(g => g !== clickedGlyph);
            } else {
                // Sélectionner (si moins de 2 déjà sélectionnés)
                if (selectedGlyphs.length < 2) {
                    clickedGlyph.isSelected = true;
                    selectedGlyphs.push(clickedGlyph);
                } else {
                    // Si 2 sont déjà sélectionnés, désélectionner le premier et sélectionner le nouveau
                    const firstSelected = selectedGlyphs.shift(); // Retire le premier
                     if(firstSelected) firstSelected.isSelected = false;
                     clickedGlyph.isSelected = true;
                    selectedGlyphs.push(clickedGlyph); // Ajoute le nouveau
                }
            }
        } else {
            // Clic en dehors : tout désélectionner
            selectedGlyphs.forEach(g => g.isSelected = false);
            selectedGlyphs = [];
        }

        updateUIState();
        requestAnimationFrame(drawAllGlyphs); // Utiliser requestAnimationFrame
    }

    function generateNewGlyph(mode = 'auto', rules = {}) {
        // Trouve une position non superposée (méthode simple)
        let x, y, attempts = 0, overlaps;
        const maxAttempts = 50;
        const padding = 10; // Marge par rapport aux bords
         // Utiliser la taille effective (style CSS) pour le placement
        const effectiveWidth = parseFloat(canvas.style.width);
        const effectiveHeight = parseFloat(canvas.style.height);


        do {
            overlaps = false;
             // Ajuster les plages pour prendre en compte la taille du glyphe et le padding
            const minX = BASE_GLYPH_SIZE / 2 + padding;
            const maxX = effectiveWidth - BASE_GLYPH_SIZE / 2 - padding;
            const minY = BASE_GLYPH_SIZE / 2 + padding;
            const maxY = effectiveHeight - BASE_GLYPH_SIZE / 2 - padding;

             // Vérifier si la plage est valide (le canvas est assez grand)
             if (maxX < minX || maxY < minY) {
                 console.warn("Canvas trop petit pour placer le glyphe avec padding.");
                 // Placer au centre par défaut ou gérer autrement
                 x = effectiveWidth / 2;
                 y = effectiveHeight / 2;
                 break; // Sortir de la boucle si le canvas est trop petit
             }

            x = randomRange(minX, maxX);
            y = randomRange(minY, maxY);

            for (const existingGlyph of currentGlyphs) {
                const distSq = (x - existingGlyph.x)**2 + (y - existingGlyph.y)**2;
                // Vérifier si les cercles englobants se chevauchent
                if (distSq < (BASE_GLYPH_SIZE)**2) { // Distance entre centres < somme des rayons (GlyphSize)
                    overlaps = true;
                    break;
                }
            }
            attempts++;
        } while (overlaps && attempts < maxAttempts);

        if (attempts === maxAttempts) {
            console.warn("Placement non optimal, risque de superposition.");
        }

        const newGlyph = new Glyph(x, y); // Utilise les méthodes internes pour shapes/props
        currentGlyphs.push(newGlyph);
        requestAnimationFrame(drawAllGlyphs);
        updateUIState(); // Mettre à jour l'interface (analyse, etc.)
    }

    // --- Symbolic Combination Logic ---

    function calculateSymbolicCompatibility(glyph1, glyph2) {
        let score = 0;
        const reasons = [];

        // 1. Polarité: Opposés s'attirent, identiques se repoussent (sauf neutre)
        if (glyph1.properties.polarity === '+' && glyph2.properties.polarity === '-') score += 2;
        else if (glyph1.properties.polarity === '-' && glyph2.properties.polarity === '+') score += 2;
        else if (glyph1.properties.polarity === glyph2.properties.polarity && glyph1.properties.polarity !== '0') score -= 1;
        else if (glyph1.properties.polarity === '0' || glyph2.properties.polarity === '0') score += 1; // Neutre est compatible

        if (score > 0) reasons.push(`Polarités (${glyph1.properties.polarity}, ${glyph2.properties.polarity}) complémentaires ou neutres.`);
        else if (score < 0) reasons.push(`Polarités (${glyph1.properties.polarity}, ${glyph2.properties.polarity}) identiques non-neutres.`);


        // 2. Fréquence: Proximité = résonance
        const freqDiff = Math.abs(glyph1.properties.frequency - glyph2.properties.frequency);
        const maxFreqDiff = SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE[1] - SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE[0];
        const freqSimilarity = 1 - (freqDiff / maxFreqDiff); // Score entre 0 et 1
        score += freqSimilarity * 2; // Poids de 2 pour la fréquence
         if (freqSimilarity > 0.7) reasons.push(`Fréquences (${glyph1.properties.frequency}, ${glyph2.properties.frequency}) proches (Résonance: ${freqSimilarity.toFixed(2)}).`);
         else reasons.push(`Fréquences (${glyph1.properties.frequency}, ${glyph2.properties.frequency}) distantes (Résonance: ${freqSimilarity.toFixed(2)}).`);


        // 3. Alignement: Identique = harmonie, Certains alignements peuvent être 'opposés' (simplifié ici)
        if (glyph1.properties.alignment === glyph2.properties.alignment) {
            score += 1.5;
            reasons.push(`Alignements (${glyph1.properties.alignment}) identiques.`);
        } else {
            // Logique plus complexe possible ici (ex: celestial vs chthonic = conflit ?)
            score -= 0.5; // Légère pénalité pour alignements différents
            reasons.push(`Alignements (${glyph1.properties.alignment}, ${glyph2.properties.alignment}) différents.`);
        }

        // 4. Poids Énergétique: Différence de poids peut créer déséquilibre
        const weightDiff = Math.abs(glyph1.properties.weight - glyph2.properties.weight);
        const maxWeightDiff = SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[1] - SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[0];
        const weightBalance = 1 - (weightDiff / maxWeightDiff); // Score entre 0 et 1
        score += weightBalance * 1; // Poids de 1 pour l'équilibre des poids
        if (weightBalance > 0.6) reasons.push(`Poids (${glyph1.properties.weight}, ${glyph2.properties.weight}) équilibrés (Équilibre: ${weightBalance.toFixed(2)}).`);
        else reasons.push(`Poids (${glyph1.properties.weight}, ${glyph2.properties.weight}) déséquilibrés (Équilibre: ${weightBalance.toFixed(2)}).`);


        // Normalisation simple du score (exemple, plage à ajuster)
        // Le score max théorique est ~ 2 + 2 + 1.5 + 1 = 6.5
        // Le score min théorique est ~ -1 + 0 - 0.5 + 0 = -1.5
         const normalizedScore = normalize(score, -1.5, 6.5); // Mappe sur [0, 1]

        let compatibilityLevel = 'neutre';
        if (normalizedScore > 0.7) compatibilityLevel = 'compatible';
        else if (normalizedScore < 0.4) compatibilityLevel = 'incompatible';

        return { score: score.toFixed(2), normalized: normalizedScore.toFixed(2), level: compatibilityLevel, reasons };
    }

    function combineSelectedGlyphs() {
        if (selectedGlyphs.length !== 2) return;

        const [glyph1, glyph2] = selectedGlyphs;
        const compatibility = calculateSymbolicCompatibility(glyph1, glyph2);
        console.log("Compatibilité:", compatibility); // Log pour debug

        // --- Logique de Fusion ---
        // 1. Formes: Prendre un sous-ensemble + ajout potentiel d'une forme 'liante'
        const shapes1 = deepClone(glyph1.shapes);
        const shapes2 = deepClone(glyph2.shapes);
        const newShapes = [];
        const numToTake = Math.min(shapes1.length, shapes2.length, randomInt(1, 3)); // Prendre 1 à 3 de chaque max

        // Prendre aléatoirement de chaque parent
        for (let i = 0; i < numToTake; i++) {
            if (shapes1.length > 0) newShapes.push(shapes1.splice(randomInt(0, shapes1.length - 1), 1)[0]);
            if (shapes2.length > 0) newShapes.push(shapes2.splice(randomInt(0, shapes2.length - 1), 1)[0]);
        }

         // Optionnel : Ajouter une petite forme centrale symbolisant la fusion
         newShapes.push({
             type: 'circle', x: 0, y: 0, radius: BASE_GLYPH_SIZE * 0.05,
             symbolicHints: { polarity: '0', freqMod: 1, weightMod: 0.5, alignmentHint: 'terrestrial' } // Neutre et léger
         });

        // Ajuster les positions relatives des formes héritées pour éviter la superposition exacte
         newShapes.forEach(shape => {
             shape.x += randomRange(-5, 5);
             shape.y += randomRange(-5, 5);
         });


        // 2. Propriétés: Calculer les nouvelles propriétés basées sur les parents et la compatibilité
        const newProps = {};

        // Nouvelle Polarité: Influence par compatibilité et poids
        if (glyph1.properties.polarity === glyph2.properties.polarity) {
            newProps.polarity = glyph1.properties.polarity;
        } else if ( (glyph1.properties.polarity === '+' && glyph2.properties.polarity === '-') ||
                    (glyph1.properties.polarity === '-' && glyph2.properties.polarity === '+') ) {
            // Opposés: tendance vers neutre, sauf si poids très déséquilibré
            if (Math.abs(glyph1.properties.weight - glyph2.properties.weight) > 5) { // Seuil arbitraire
                newProps.polarity = glyph1.properties.weight > glyph2.properties.weight ? glyph1.properties.polarity : glyph2.properties.polarity;
            } else {
                newProps.polarity = '0'; // Équilibre -> Neutre
            }
        } else { // Un des deux est neutre
            newProps.polarity = glyph1.properties.polarity !== '0' ? glyph1.properties.polarity : glyph2.properties.polarity; // Prend la polarité non-neutre
        }

        // Nouvelle Fréquence: Moyenne pondérée par le poids
        const totalWeightParents = glyph1.properties.weight + glyph2.properties.weight;
        if(totalWeightParents > 0) {
             newProps.frequency = Math.round(
                (glyph1.properties.frequency * glyph1.properties.weight + glyph2.properties.frequency * glyph2.properties.weight) / totalWeightParents
             );
        } else {
             newProps.frequency = Math.round((glyph1.properties.frequency + glyph2.properties.frequency) / 2); // Moyenne simple si poids nuls
        }
         newProps.frequency = Math.max(SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE[0], Math.min(SYMBOLIC_PROPERTIES.BASE_FREQUENCY_RANGE[1], newProps.frequency)); // Clamp


        // Nouveau Poids: Somme + bonus/malus léger selon compatibilité ?
        newProps.weight = glyph1.properties.weight + glyph2.properties.weight;
        if (compatibility.level === 'compatible') newProps.weight *= 1.1; // Synergie
        else if (compatibility.level === 'incompatible') newProps.weight *= 0.9; // Tension/Perte
        newProps.weight = Math.round(Math.max(SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[0], Math.min(SYMBOLIC_PROPERTIES.BASE_WEIGHT_RANGE[1]*1.5, newProps.weight))); // Clamp (permet dépassement léger)


        // Nouvel Alignement: Si identiques, garder. Sinon, 'mixte' ou celui du plus 'lourd' ?
        if (glyph1.properties.alignment === glyph2.properties.alignment) {
            newProps.alignment = glyph1.properties.alignment;
        } else {
             // Règle simple : celui du glyphe le plus lourd domine
             newProps.alignment = glyph1.properties.weight >= glyph2.properties.weight ? glyph1.properties.alignment : glyph2.properties.alignment;
             // Alternative: introduire un alignement 'mixed'
        }

        // Nouvelles Valeurs Associées: Fusionner les listes en évitant les doublons + tag de fusion
        const combinedValues = new Set([...glyph1.properties.values, ...glyph2.properties.values]);
        combinedValues.add('fused'); // Tag indiquant une fusion
         combinedValues.add(`compat:${compatibility.level}`); // Tag de compatibilité
        newProps.values = Array.from(combinedValues);

        // 3. Position: Au milieu des parents
        const newX = (glyph1.x + glyph2.x) / 2;
        const newY = (glyph1.y + glyph2.y) / 2;

        // 4. Créer le nouveau glyphe
        const fusedGlyph = new Glyph(newX, newY, generateUUID(), newShapes, newProps); // Passer les nouvelles shapes et props

        // 5. Remplacer les anciens par le nouveau
        currentGlyphs = currentGlyphs.filter(g => g !== glyph1 && g !== glyph2);
        currentGlyphs.push(fusedGlyph);

        // 6. Nettoyer la sélection et l'UI
        selectedGlyphs = [];
        updateUIState();
        requestAnimationFrame(drawAllGlyphs);
    }

    // --- Archive Management ---

    function saveGlyphsToArchive(glyphsToSave) {
         glyphsToSave.forEach(glyph => {
            const clone = deepClone(glyph);
            if (clone && !glyphArchive.some(g => g.id === clone.id)) { // Évite doublons d'ID exact
                 clone.isSelected = false; // Assurer qu'il n'est pas sélectionné dans l'archive
                glyphArchive.push(clone);
            } else if (!clone) {
                 console.error("Échec du clonage du glyphe pour l'archivage.");
            } else {
                 console.log(`Glyphe ${clone.id} déjà dans l'archive.`);
            }
         });
         displayArchive();
         updateUIState(); // Pour désactiver "Archiver" si plus rien n'est sélectionné
         saveArchiveToLocalStorage(); // Persister
    }

     function deleteFromArchive(glyphId) {
        glyphArchive = glyphArchive.filter(g => g.id !== glyphId);
        if (selectedArchiveId === glyphId) {
            selectedArchiveId = null; // Désélectionner si l'élément supprimé était sélectionné
        }
        displayArchive();
        saveArchiveToLocalStorage();
    }

     function displayArchive(filter = "") {
        archiveList.innerHTML = ''; // Vider la liste
        const filteredArchive = glyphArchive.filter(glyph => {
            if (!filter) return true;
            const searchTerm = filter.toLowerCase();
            return (
                glyph.id.toLowerCase().includes(searchTerm) ||
                glyph.properties.polarity.toLowerCase().includes(searchTerm) ||
                glyph.properties.alignment.toLowerCase().includes(searchTerm) ||
                glyph.properties.values.some(val => val.toLowerCase().includes(searchTerm)) ||
                glyph.properties.frequency.toString().includes(searchTerm) ||
                glyph.properties.weight.toString().includes(searchTerm)
            );
        });

        if (filteredArchive.length === 0) {
            archiveList.innerHTML = '<li>Aucun glyphe trouvé ou archive vide.</li>';
            return;
        }

        filteredArchive.forEach(glyph => {
            const li = document.createElement('li');
            li.dataset.id = glyph.id;
            li.classList.toggle('selected-archive', glyph.id === selectedArchiveId); // Appliquer la classe si sélectionné

             // Affichage textuel simplifié des propriétés clés
             let textContent = `ID: ${glyph.id.substring(0, 6)}... | P:${glyph.properties.polarity} | F:${glyph.properties.frequency} | W:${glyph.properties.weight} | A:${glyph.properties.alignment}`;
             if (glyph.properties.values.includes('fused')) {
                textContent += " (Fusionné)";
             }

             const textSpan = document.createElement('span');
             textSpan.textContent = textContent;
             textSpan.title = JSON.stringify(glyph.properties, null, 2); // Tooltip avec détails

             const deleteBtn = document.createElement('button');
             deleteBtn.textContent = '✕'; // Croix pour supprimer
             deleteBtn.classList.add('delete-glyph');
             deleteBtn.title = 'Supprimer de l\'archive';
             deleteBtn.onclick = (e) => {
                 e.stopPropagation(); // Empêche le clic de sélectionner l'élément li
                 if (confirm(`Supprimer le glyphe ${glyph.id.substring(0,6)}... de l'archive ?`)) {
                     deleteFromArchive(glyph.id);
                 }
             };


            li.appendChild(textSpan);
             li.appendChild(deleteBtn);

            li.onclick = () => {
                // Gérer la sélection dans l'archive
                 if (selectedArchiveId === glyph.id) {
                     // Désélectionner si on clique à nouveau sur l'élément sélectionné
                     selectedArchiveId = null;
                 } else {
                     selectedArchiveId = glyph.id;
                 }
                 displayArchive(searchArchiveInput.value); // Redessiner pour màj la classe selected
                 // Afficher les détails du glyphe archivé sélectionné dans le panneau d'analyse
                 displayGlyphAnalysis([glyph]);
            };

            archiveList.appendChild(li);
        });
    }

    function handleSearchArchive() {
        displayArchive(searchArchiveInput.value);
    }

     function clearArchive() {
        if (confirm("Êtes-vous sûr de vouloir vider toute l'archive ? Cette action est irréversible.")) {
             glyphArchive = [];
             selectedArchiveId = null;
             displayArchive();
             saveArchiveToLocalStorage();
        }
    }

    // --- Data Export/Import ---

    function exportArchiveToJSON() {
        if (glyphArchive.length === 0) {
            alert("L'archive est vide. Rien à exporter.");
            return;
        }
        const jsonString = JSON.stringify(glyphArchive, null, 2); // Indentation pour lisibilité
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const timestamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-');
        a.download = `glyph_archive_${timestamp}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log("Archive exportée.");
    }

    function handleImportFile(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const importedData = JSON.parse(e.target.result);
                if (Array.isArray(importedData)) {
                     // Vérification simple de la structure (pourrait être plus robuste)
                     if (importedData.length === 0 || (importedData[0].id && importedData[0].shapes && importedData[0].properties)) {
                         // Fusionner ou remplacer ? Ici, on ajoute sans vérifier les doublons complexes.
                         // Pour une fusion plus intelligente, il faudrait comparer les IDs existants.
                         const newGlyphs = importedData.filter(g => g.id && !glyphArchive.some(existing => existing.id === g.id));
                         const existingCount = importedData.length - newGlyphs.length;

                         glyphArchive.push(...newGlyphs); // Ajoute seulement les nouveaux
                         saveArchiveToLocalStorage();
                         displayArchive();
                         alert(`Importation terminée. ${newGlyphs.length} nouveaux glyphes ajoutés. ${existingCount > 0 ? existingCount + ' glyphes existants ignorés.' : ''}`);
                     } else {
                         throw new Error("Format de données invalide. Le fichier JSON doit être un tableau de glyphes valides.");
                     }
                } else {
                     throw new Error("Format de données invalide. Le fichier JSON doit contenir un tableau.");
                }
            } catch (error) {
                console.error("Erreur lors de l'importation:", error);
                alert(`Erreur lors de l'importation: ${error.message}`);
            } finally {
                 // Réinitialiser l'input file pour permettre de réimporter le même fichier
                importFileInput.value = '';
            }
        };
        reader.onerror = (e) => {
            console.error("Erreur de lecture du fichier:", e);
            alert("Erreur de lecture du fichier.");
            importFileInput.value = '';
        };
        reader.readAsText(file);
    }

     // --- Persistence (LocalStorage) ---
    const STORAGE_KEY = 'glyphSymbolToolArchive';

    function saveArchiveToLocalStorage() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(glyphArchive));
        } catch (e) {
            console.error("Erreur lors de la sauvegarde dans LocalStorage:", e);
             alert("Impossible de sauvegarder l'archive (peut-être que le stockage est plein).");
        }
    }

    function loadArchiveFromLocalStorage() {
        const savedData = localStorage.getItem(STORAGE_KEY);
        if (savedData) {
            try {
                glyphArchive = JSON.parse(savedData);
                console.log(`Archive chargée depuis LocalStorage (${glyphArchive.length} glyphes).`);
            } catch (e) {
                console.error("Erreur lors du chargement depuis LocalStorage:", e);
                glyphArchive = []; // Reset en cas d'erreur
                localStorage.removeItem(STORAGE_KEY); // Nettoyer les données corrompues
            }
        } else {
            glyphArchive = []; // Initialiser si rien n'est sauvegardé
        }
         displayArchive(); // Afficher l'archive chargée
    }


    // --- UI Update Functions ---

    function displayGlyphAnalysis(glyphsToAnalyze) {
        analysisContent.innerHTML = ''; // Clear previous content
        compatibilityScoreDiv.innerHTML = ''; // Clear compatibility
        compatibilityScoreDiv.className = ''; // Reset class

        if (glyphsToAnalyze.length === 0) {
            analysisContent.innerHTML = '<p>Sélectionnez un glyphe sur le canvas ou dans l\'archive pour voir ses détails.</p>';
            return;
        }

        glyphsToAnalyze.forEach((glyph, index) => {
            const div = document.createElement('div');
            div.style.marginBottom = '15px';
            div.style.borderBottom = index < glyphsToAnalyze.length - 1 ? '1px dashed #ccc' : 'none'; // Separator
             div.style.paddingBottom = index < glyphsToAnalyze.length - 1 ? '10px' : '0';

             let title = `Glyphe ${index + 1}: ${glyph.id.substring(0, 8)}...`;
             // Indiquer si le glyphe vient de l'archive
             if (glyphArchive.some(archived => archived.id === glyph.id) && !currentGlyphs.some(current => current.id === glyph.id)) {
                title += " (depuis Archive)";
             } else if (glyphArchive.some(archived => archived.id === glyph.id) ) {
                 title += " (sur Canvas & Archivé)";
             }
             else {
                 title += " (sur Canvas)";
             }


            div.innerHTML = `<strong>${title}</strong>`;
            const ul = document.createElement('ul');
            ul.innerHTML = `
                <li>Polarité: ${glyph.properties.polarity}</li>
                <li>Fréquence Vibratoire: ${glyph.properties.frequency}</li>
                <li>Poids Énergétique: ${glyph.properties.weight}</li>
                <li>Alignement Symbolique: ${glyph.properties.alignment}</li>
                <li>Valeurs Associées: ${glyph.properties.values.join(', ') || 'Aucune'}</li>
                <li>Nombre de Formes: ${glyph.shapes.length}</li>
                <li>Position (Canvas): ${glyph.x ? glyph.x.toFixed(1) : 'N/A'}, ${glyph.y ? glyph.y.toFixed(1) : 'N/A'}</li>
            `;
            div.appendChild(ul);
            analysisContent.appendChild(div);
        });

        // Afficher la compatibilité si deux glyphes sont sélectionnés
        if (glyphsToAnalyze.length === 2) {
            const compatibility = calculateSymbolicCompatibility(glyphsToAnalyze[0], glyphsToAnalyze[1]);
            compatibilityScoreDiv.innerHTML = `
                <strong>Compatibilité: ${compatibility.level.toUpperCase()}</strong> (Score: ${compatibility.score}, Norm: ${compatibility.normalized})<br>
                <small>${compatibility.reasons.join('<br>')}</small>
            `;
            compatibilityScoreDiv.classList.add(compatibility.level); // Ajoute classe compatible/incompatible/neutral
        }
    }

    function updateUIState() {
        // Mettre à jour l'état des boutons
        combineBtn.disabled = selectedGlyphs.length !== 2;
        saveSelectedBtn.disabled = selectedGlyphs.length === 0;

        // Mettre à jour le panneau d'analyse
        displayGlyphAnalysis(selectedGlyphs.length > 0 ? selectedGlyphs : (selectedArchiveId ? [glyphArchive.find(g => g.id === selectedArchiveId)].filter(Boolean) : []));

         // On pourrait aussi mettre à jour l'état du bouton "Générer (Règles)" ici si implémenté
    }

    // --- Event Listeners ---
    genAutoBtn.addEventListener('click', () => generateNewGlyph('auto'));
    // genRuleBtn.addEventListener('click', () => generateNewGlyph('rules', { /* Passer les règles ici */ })); // Placeholder
    combineBtn.addEventListener('click', combineSelectedGlyphs);
    clearCanvasBtn.addEventListener('click', () => {
        currentGlyphs = [];
        selectedGlyphs = [];
        updateUIState();
        requestAnimationFrame(drawAllGlyphs);
    });
    saveSelectedBtn.addEventListener('click', () => {
        saveGlyphsToArchive(selectedGlyphs);
        // Optionnel: désélectionner après archivage ?
        selectedGlyphs.forEach(g => g.isSelected = false);
        selectedGlyphs = [];
        updateUIState();
        requestAnimationFrame(drawAllGlyphs);
    });
    exportArchiveBtn.addEventListener('click', exportArchiveToJSON);
    importFileLabel.addEventListener('click', () => importFileInput.click()); // Déclenche clic sur input caché
    importFileInput.addEventListener('change', handleImportFile);
    searchArchiveInput.addEventListener('input', handleSearchArchive);
     clearArchiveBtn.addEventListener('click', clearArchive);

    canvas.addEventListener('click', handleCanvasClick);

    // --- Initialization ---
    loadArchiveFromLocalStorage(); // Charger l'archive persistée
    updateUIState(); // Set initial button states etc.
    // requestAnimationFrame(drawAllGlyphs); // Le premier draw est déjà appelé par resizeCanvas
    console.log("Moteur de glyphes initialisé pour Syn.");
});