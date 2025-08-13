// glyphUtils.js

// --- Constantes Symboliques (Exemples) ---
const SYMBOLIC_PROPERTIES = {
    POLARITY: ['+', '-', '0'], // Positif, Négatif, Neutre
    ALIGNMENT: ['celestial', 'terrestrial', 'chthonic', 'void', 'elemental'], // Exemples d'alignements
    BASE_FREQUENCY_RANGE: [1, 100],
    BASE_WEIGHT_RANGE: [1, 10],
};

const SHAPE_SYMBOL_MAP = { // Associe formes à des tendances symboliques (simplifié)
    circle: { polarityBias: '0', freqMod: 1.0, weightMod: 1.2, alignmentHint: ['celestial', 'terrestrial'] },
    triangle: { polarityBias: ['+', '-'], freqMod: 1.1, weightMod: 1.0, alignmentHint: ['elemental', 'chthonic'] }, // Peut être + ou -
    line: { polarityBias: '0', freqMod: 0.9, weightMod: 0.8, alignmentHint: ['terrestrial', 'void'] },
    arc: { polarityBias: '0', freqMod: 1.05, weightMod: 1.1, alignmentHint: ['celestial', 'elemental'] },
};

// --- Fonctions Utilitaires ---

function randomRange(min, max) {
    return Math.random() * (max - min) + min;
}

function randomInt(min, max) {
    return Math.floor(randomRange(min, max + 1));
}

function randomChoice(arr) {
    if (!arr || arr.length === 0) return undefined;
    return arr[Math.floor(Math.random() * arr.length)];
}

// Génère un ID unique simple (pas un vrai UUID mais suffisant ici)
function generateUUID() {
    return Date.now().toString(36) + Math.random().toString(36).substring(2, 7);
}

// Fonction de clonage profond simple (pour l'archivage)
function deepClone(obj) {
    try {
        return JSON.parse(JSON.stringify(obj));
    } catch (e) {
        console.error("Erreur de clonage:", e);
        return null; // ou gérer l'erreur autrement
    }
}

// Fonction pour normaliser une valeur dans une plage [0, 1]
function normalize(value, min, max) {
    if (max === min) return 0.5; // Éviter division par zéro
    return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

// Fonction pour obtenir les coordonnées du clic sur le canvas
function getCanvasMousePos(canvas, event) {
     const rect = canvas.getBoundingClientRect();
     // Prend en compte le style CSS qui ajuste la taille du canvas
     const scaleX = canvas.width / rect.width;
     const scaleY = canvas.height / rect.height;
     const x = (event.clientX - rect.left) * scaleX;
     const y = (event.clientY - rect.top) * scaleY;
     return { x, y };
}

// --- Fonctions de Dessin de Formes ---
function drawShape(ctx, shape, offsetX = 0, offsetY = 0) {
    ctx.beginPath();
    const x = shape.x + offsetX;
    const y = shape.y + offsetY;

    switch (shape.type) {
        case 'circle':
            ctx.arc(x, y, shape.radius, 0, Math.PI * 2);
            break;
        case 'triangle':
            ctx.save();
            ctx.translate(x, y);
            ctx.rotate(shape.angle);
            const h = shape.size * (Math.sqrt(3) / 2);
            ctx.moveTo(0, -h / 2);
            ctx.lineTo(-shape.size / 2, h / 2);
            ctx.lineTo(shape.size / 2, h / 2);
            ctx.closePath();
            ctx.restore();
            break;
        case 'line':
            // Ajustement pour que les lignes soient aussi relatives à shape.x, shape.y
             const dx = Math.cos(shape.angle) * shape.length / 2;
             const dy = Math.sin(shape.angle) * shape.length / 2;
             ctx.moveTo(x - dx, y - dy);
             ctx.lineTo(x + dx, y + dy);
            break;
        case 'arc':
             ctx.arc(x, y, shape.radius, shape.startAngle, shape.endAngle);
             break;
        // Ajouter d'autres formes si nécessaire
        default:
            console.warn("Type de forme inconnu:", shape.type);
            return; // Ne pas essayer de dessiner
    }
     ctx.stroke(); // Dessine le contour
}