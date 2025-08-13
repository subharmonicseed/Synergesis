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

    // --- Symbolic 
(Content truncated due to size limit. Use line ranges to read in chunks)