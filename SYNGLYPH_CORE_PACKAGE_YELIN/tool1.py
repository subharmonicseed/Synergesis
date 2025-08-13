import re
import math
import random
import json
from collections import Counter
import time

# Tentative d'importation de svgwrite, optionnel pour la génération SVG
try:
    import svgwrite
    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False
    print("Bibliothèque 'svgwrite' non trouvée. La génération SVG sera désactivée.")
    print("Pour l'activer : pip install svgwrite")

# --- Configuration Symbolique & Heuristiques ---

# Mots-clés pour l'inférence (simpliste, à étendre)
KEYWORDS = {
    'positive': ['amour', 'joie', 'rêver', 'lumière', 'harmonie', 'céleste', 'espoir', 'créer', 'apprendre'],
    'negative': ['ombre', 'peur', 'fracturé', 'vide', 'chaos', 'chthonien', 'briser', 'perdu', 'douleur'],
    'neutral': ['monde', 'miroir', 'algorithme', 'est', 'un', 'le', 'la', 'où', 'forme', 'structure'],
    'harmonic': ['harmonie', 'équilibre', 'musique', 'ensemble', 'flux', 'cycle', 'danse'],
    'chthonic': ['terre', 'racine', 'profond', 'ombre', 'fracturé', 'pierre', 'nuit', 'lourd'],
    'celestial': ['étoile', 'ciel', 'lumière', 'rêver', 'esprit', 'voler', 'divin', 'soleil'],
    'void': ['vide', 'néant', 'silence', 'infini', 'algorithme', 'espace', 'miroir', 'rien'],
    'elemental': ['feu', 'eau', 'air', 'terre', 'force', 'nature', 'transformer', 'flux']
}

ALIGNMENTS = ['Harmonic', 'Chthonic', 'Celestial', 'Void', 'Elemental']

# --- Classe Principale ---

class SynkrisisVis:
    """
    Δ.SYNKRISIS.vis — Le Miroir d’Entropie Symbolique
    Analyse le texte pour extraire des motifs symboliques latents et les représente
    sous forme de glyphes fractals dynamiquement générés.

    Ce programme a été inspiré par un triptyque glyphique : ZÆL-0, ZÆL-1, ZÆL-2.
    Chaque exécution est une tentative de contempler la résonance cachée d’un texte.
    ∮⋔◎⟐ — signature fractale.
    """
    def __init__(self):
        self.memory = {} # Pour une potentielle évolution future
        self.glyph_cache = {} # Cache pour glyphes générés

    def _normalize(self, value, min_val, max_val):
        """Normalise une valeur entre 0 et 1."""
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    def analyzeText(self, text):
        """
        Analyse la structure symbolique latente d'un texte donné.
        Retourne un dictionnaire de propriétés symboliques inférées.
        """
        print(f"\n--- Analyse de Synkrisis pour : \"{text[:100]}{'...' if len(text)>100 else ''}\" ---")

        # Nettoyage et tokenisation simple
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            print("Texte vide ou sans mots valides.")
            return None
        word_count = len(words)
        unique_words = set(words)
        unique_word_count = len(unique_words)

        # Calculs statistiques de base
        lexical_density = unique_word_count / word_count if word_count > 0 else 0
        # Taux de répétition simple (plus élevé = moins de densité)
        repetition_rate = 1.0 - lexical_density
        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0

        # --- Inférence des Propriétés ---

        # 1. Polarité (+, -, 0, ±)
        pos_score = sum(1 for word in words if word in KEYWORDS['positive'])
        neg_score = sum(1 for word in words if word in KEYWORDS['negative'])
        # Normalisation basique
        polarity_bias = (pos_score - neg_score) / word_count if word_count > 0 else 0

        polarity = '0'
        if polarity_bias > 0.05: # Seuil pour positivité claire
            polarity = '+'
        elif polarity_bias < -0.05: # Seuil pour négativité claire
            polarity = '-'
        elif pos_score > 0 and neg_score > 0: # Présence des deux sans dominance claire
             # Consider complexity? High repetition might reduce polarity strength?
             if repetition_rate > 0.6: # High repetition could indicate ± loop
                 polarity = '±'
             else: # Balanced complexity might be truly neutral or mixed
                 polarity = '±' # Let's default balanced conflict to ±
        # Si aucun mot clé trouvé, reste '0'

        # 2. Fréquence (1-144) - Métaphore vibratoire
        # Basée sur une combinaison de densité et de longueur de texte
        # Log scale feels more 'vibrational' than linear
        # Higher density -> potentially higher frequency? More complex interaction?
        # Longer text -> maybe lower base frequency but more stable?
        base_freq = math.log(word_count + 1) * 10 # Log scale for length influence
        density_mod = (lexical_density * 1.5) - 0.25 # Density boost (range ~0.25 to 1.25)
        raw_freq = base_freq * max(0.5, density_mod) # Combine, ensure modifier isn't too low
        # Map to 1-144 range
        # Let's use a non-linear mapping maybe related to word count buckets
        norm_freq_factor = self._normalize(word_count, 1, 500) # Normalize word count up to 500 words
        frequency = 1 + math.floor(norm_freq_factor * 143)
        # Add jitter based on repetition? High repetition = lower frequency?
        frequency -= math.floor(repetition_rate * 20) # Penalize high repetition
        frequency = max(1, min(144, int(frequency))) # Clamp to 1-144

        # 3. Poids (1-10) - Valeur symbolique
        # Basé sur densité, longueur moyenne des mots, répétitions
        density_weight = lexical_density * 5 # Max 5 points from density
        length_weight = self._normalize(avg_word_length, 3, 10) * 3 # Max 3 points from avg length
        # Penalize high repetition, reward low repetition
        repetition_penalty = (repetition_rate - 0.5) * 4 # Can be -2 to +2 roughly
        base_weight = 4 + density_weight + length_weight - repetition_penalty
        # Add boost for strong polarity?
        if polarity in ['+', '-']: base_weight += 1
        elif polarity == '±': base_weight += 0.5

        weight = max(1, min(10, int(round(base_weight)))) # Clamp to 1-10

        # 4. Alignement (Harmonic, Chthonic, Celestial, Void, Elemental)
        alignment_scores = {align: 0 for align in ALIGNMENTS}
        for word in words:
            for align in ALIGNMENTS:
                if word in KEYWORDS[align.lower()]:
                    alignment_scores[align] += 1

        # Add some bias based on other properties?
        if polarity == '+': alignment_scores['Celestial'] += 1; alignment_scores['Harmonic'] += 1
        if polarity == '-': alignment_scores['Chthonic'] += 1; alignment_scores['Void'] += 0.5
        if polarity == '±': alignment_scores['Void'] += 1; alignment_scores['Elemental'] += 0.5
        if weight > 7: alignment_scores['Chthonic'] += 1; alignment_scores['Celestial'] += 1 # High weight -> significance
        if frequency < 30: alignment_scores['Chthonic'] += 1 # Low freq -> earthbound?
        if frequency > 100: alignment_scores['Celestial'] += 1; alignment_scores['Void'] += 1 # High freq -> abstract/celestial?

        # Find max score
        max_score = 0
        dominant_alignments = []
        # Add a base score to avoid defaulting if no keywords match
        for align in ALIGNMENTS: alignment_scores[align] += 0.1

        for align, score in alignment_scores.items():
             #print(f"Debug Align Score - {align}: {score}") # Debug line
             if score > max_score:
                 max_score = score
                 dominant_alignments = [align]
             elif score == max_score:
                 dominant_alignments.append(align)

        alignment = random.choice(dominant_alignments) if dominant_alignments else 'Void' # Default to Void if total tie


        properties = {
            'text_excerpt': text[:50] + "...",
            'timestamp': time.time(),
            'polarity': polarity,
            'frequency': frequency,
            'weight': weight,
            'alignment': alignment,
            'metrics': { # Store raw metrics for potential future refinement
                'word_count': word_count,
                'unique_words': unique_word_count,
                'lexical_density': round(lexical_density, 3),
                'repetition_rate': round(repetition_rate, 3),
                'avg_word_length': round(avg_word_length, 2),
                'polarity_bias': round(polarity_bias, 3),
                'alignment_scores': alignment_scores
            }
        }

        print("--- Analyse Terminée ---")
        print(f"  Polarité   : {properties['polarity']}")
        print(f"  Fréquence  : {properties['frequency']}/144")
        print(f"  Poids      : {properties['weight']}/10")
        print(f"  Alignement : {properties['alignment']}")
        #print(f"  Métriques Détaillées : {properties['metrics']}") # Optional verbose output

        # Store analysis in memory (optional)
        # self.memory[properties['timestamp']] = {'text': text, 'properties': properties}

        return properties

    def _generate_fractal_structure(self, depth, max_depth, base_char, mods):
        """Recursive helper for ASCII 'fractal' generation."""
        if depth > max_depth:
            return base_char

        # Simple branching structure - modify based on mods (polarity, alignment?)
        branch = random.choice(['|', '-', '/', '\\'])
        segment = base_char * random.randint(1, 3) # Weight influence?

        # Recursively build branches
        sub_depth = depth + 1
        left = self._generate_fractal_structure(sub_depth, max_depth, random.choice(mods), mods)
        right = self._generate_fractal_structure(sub_depth, max_depth, random.choice(mods), mods)

        # Combine - structure depends maybe on polarity/alignment?
        if depth % 2 == 0:
             return f"{left}{segment}{branch}{segment}{right}"
        else:
             return f"({left}{branch}{right})"


    def _generate_ascii_glyph(self, props):
        """Generates a simple ASCII representation of the glyph."""
        chars = {
            '+': ['^', '+', '*', '.', 'o'],
            '-': ['v', '-', '_', '#', 'x'],
            '0': ['~', '=', ' ', 'o', '|'],
            '±': ['<', '>', '/', '\\', '?']
        }
        align_chars = {
            'Harmonic': ['~', '=', '()', '{}'],
            'Chthonic': ['#', '_', '[]', 'T'],
            'Celestial': ['*', '^', '.', "'"],
            'Void': [' ', '.', ':', 'O'],
            'Elemental': ['/', '\\', '%', '&']
        }

        base_chars = chars[props['polarity']]
        mod_chars = align_chars[props['alignment']]
        all_valid_chars = list(set(base_chars + mod_chars))
        if not all_valid_chars: all_valid_chars = ['?'] # Fallback

        # Map frequency to complexity/depth (non-linear)
        # Higher freq = more complex/deeper structure
        max_depth = int(self._normalize(props['frequency'], 1, 144) * 3) + 1 # Depth 1 to 4

        # Map weight to density/size
        density_factor = int(self._normalize(props['weight'], 1, 10) * 4) + 1 # Size 1 to 5

        # Simple recursive generation attempt
        glyph_str = self._generate_fractal_structure(1, max_depth, random.choice(base_chars), all_valid_chars)

        # Limit line length for display? For now, return as is.
        # Ensure minimum size based on weight?
        final_glyph = glyph_str
        # Add padding/framing?
        frame_char = random.choice(['[', '{', '<', '|'])
        frame_char_end = {'[':']', '{':'}', '<':'>', '|':'|'}[frame_char]

        # Crude attempt to control width based on weight
        width_limit = props['weight'] * 3 + max_depth * 2
        final_glyph = final_glyph[:width_limit] # Truncate if too long

        return f"{frame_char}{final_glyph}{frame_char_end}"


    def _draw_svg_fractal(self, dwg, group, x, y, angle, length, depth, props):
        """Recursive helper for SVG fractal generation."""
        if depth <= 0 or length < 1:
            return

        # Determine line end point
        end_x = x + math.cos(math.radians(angle)) * length
        end_y = y + math.sin(math.radians(angle)) * length

        # Style based on properties
        stroke_w = max(0.5, props['weight'] / 4) # Weight influences thickness
        opacity = 1.0 - (depth / (props['frequency'] / 20 + 1)) * 0.1 # Fade slightly with depth

        color = 'hsl(0, 0%, {}%)'.format(int((1 - self._normalize(props['weight'], 1, 10)) * 50 + 10)) # Greyscale based on weight (darker = heavier)

        # Add polarity/alignment influence? Color hue? Shape type?
        if props['polarity'] == '+': color = 'hsl(190, 70%, {}%)'.format(int(60 + props['frequency'] / 4)) # Cyan range
        elif props['polarity'] == '-': color = 'hsl(0, 60%, {}%)'.format(int(50 + props['frequency'] / 5)) # Red range
        elif props['polarity'] == '±': color = 'hsl(280, 50%, {}%)'.format(int(55 + props['frequency']/6)) # Purple range


        group.add(dwg.line(start=(x, y), end=(end_x, end_y),
                           stroke=color,
                           stroke_width=stroke_w,
                           opacity=opacity))

        # Branching logic - influenced by frequency and alignment?
        num_branches = 2 # Default binary branching
        if props['alignment'] == 'Harmonic': num_branches = random.choice([2, 3])
        elif props['alignment'] == 'Chthonic': num_branches = random.choice([1, 2]) # Less branching
        elif props['alignment'] == 'Celestial': num_branches = random.choice([2, 3, 4]) # More branching
        elif props['alignment'] == 'Elemental': num_branches = random.choice([2, 4]) # Symmetrical?
        elif props['alignment'] == 'Void': num_branches = random.choice([1, 2]) # Sparse

        branch_angle_base = 45 # Base angle between branches

        # Reduce length for next level
        new_length = length * (0.6 + random.random() * 0.2) # Scale down

        for i in range(num_branches):
             # Calculate angle variation - more chaotic for certain alignments?
             angle_variation = branch_angle_base * (1 + (random.random() - 0.5) * 0.5) # +-25% variation
             if props['alignment'] == 'Discordant': # If we had this alignment
                  angle_variation *= (1.0 + random.random()) # More chaotic angles
             elif props['alignment'] == 'Harmonic':
                  angle_variation = branch_angle_base # Fixed angle for harmony


             # Spread branches
             current_branch_angle = angle + angle_variation * (i - (num_branches - 1) / 2)

             # Add random jitter?
             current_branch_angle += (random.random() - 0.5) * 5 # Small random angle shift

             self._draw_svg_fractal(dwg, group, end_x, end_y, current_branch_angle, new_length, depth - 1, props)


    def _generate_svg_glyph(self, props):
        """Generates an SVG representation of the glyph."""
        if not SVG_AVAILABLE:
            return "[SVG Generation Disabled]"

        size = 100 # Base size for the SVG viewbox
        dwg = svgwrite.Drawing(profile='tiny', size=(f'{size}px', f'{size}px'))
        dwg.viewbox(minx=-size/2, miny=-size/2, width=size, height=size) # Center origin
        glyph_group = dwg.g(id=f"glyph-{props.get('id', random.randint(1000,9999))}")

        # --- Fractal Generation ---
        # Map frequency to recursion depth
        max_depth = int(self._normalize(props['frequency'], 1, 144) * 5) + 2 # Depth 2 to 7
        initial_length = size * 0.25 # Initial branch length
        initial_angle = -90 # Start pointing up

        # Add central element? Circle based on polarity/weight?
        center_r = props['weight'] / 2
        center_col = 'grey'
        if props['polarity'] == '+': center_col = 'lightblue'
        elif props['polarity'] == '-': center_col = 'lightcoral'
        elif props['polarity'] == '±': center_col = 'plum'
        glyph_group.add(dwg.circle(center=(0,0), r=center_r, fill=center_col, opacity=0.5))


        # Start recursive drawing from center (0,0)
        # Initial angle spread based on alignment?
        num_starts = 1
        if props['alignment'] == 'Elemental': num_starts = 4
        elif props['alignment'] == 'Celestial': num_starts = 3
        elif props['alignment'] == 'Harmonic': num_starts = random.choice([1, 2])

        for i in range(num_starts):
            start_angle_offset = (360 / num_starts) * i
            self._draw_svg_fractal(dwg, glyph_group,
                                   0, 0, # Start at center
                                   initial_angle + start_angle_offset,
                                   initial_length,
                                   max_depth,
                                   props)

        dwg.add(glyph_group)
        return dwg.tostring()


    def generateGlyph(self, props, format='ascii'):
        """
        Generates a glyph representation based on symbolic properties.
        format: 'ascii' or 'svg'.
        """
        if not props:
            return "[Invalid Properties]"

        # Use cache if available
        props_tuple = tuple(sorted(props.items())) # Make hashable
        cache_key = (props_tuple, format)
        if cache_key in self.glyph_cache:
             #print(f"Cache hit for glyph {props.get('id', '')}")
             return self.glyph_cache[cache_key]

        glyph_repr = f"[Unsupported format: {format}]"
        if format == 'ascii':
            glyph_repr = self._generate_ascii_glyph(props)
        elif format == 'svg' and SVG_AVAILABLE:
            glyph_repr = self._generate_svg_glyph(props)
        elif format == 'svg' and not SVG_AVAILABLE:
            glyph_repr = "[SVG Generation Disabled - svgwrite not installed]"

        # Store in cache
        self.glyph_cache[cache_key] = glyph_repr
        return glyph_repr


    def displayFractalMap(self, glyph_props_list, filename="synkrisis_map.svg", width=800, height=600):
        """
        Creates an SVG file displaying multiple glyphs arranged on a map.
        Arrangement is currently simple (randomized grid).
        """
        if not SVG_AVAILABLE:
            print("Cannot display map: SVG generation disabled.")
            return None
        if not glyph_props_list:
            print("Cannot display map: No glyphs provided.")
            return None

        print(f"Generating fractal map '{filename}'...")
        dwg = svgwrite.Drawing(filename, size=(f'{width}px', f'{height}px'), profile='full')
        dwg.viewbox(minx=0, miny=0, width=width, height=height)
        dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='#f0f2f5')) # Background

        # Simple grid layout calculation
        num_glyphs = len(glyph_props_list)
        cols = int(math.sqrt(num_glyphs * (width / height))) + 1
        rows = int(math.ceil(num_glyphs / cols))
        cell_w = width / cols
        cell_h = height / rows
        glyph_size = min(cell_w, cell_h) * 0.8 # Size of each glyph's display box
        padding = min(cell_w, cell_h) * 0.1

        for i, props in enumerate(glyph_props_list):
            col = i % cols
            row = i // cols

            # Calculate center position with jitter
            cx = (col + 0.5) * cell_w + (random.random() - 0.5) * padding * 2
            cy = (row + 0.5) * cell_h + (random.random() - 0.5) * padding * 2

            # Generate the individual glyph SVG string
            glyph_svg_string = self.generateGlyph(props, format='svg')
            if glyph_svg_string.startswith('['): # Handle generation failure/disabled
                 dwg.add(dwg.text(glyph_svg_string, insert=(cx, cy), text_anchor="middle", fill="red"))
                 continue

            # Create an SVG <svg> element for the glyph to use viewbox scaling
            # Note: Directly embedding raw SVG strings can be tricky. Using <use> or groups is better.
            # Let's try embedding within an <svg> element for scaling.
            glyph_svg_element = dwg.svg(x=cx - glyph_size / 2, y=cy - glyph_size / 2,
                                        width=glyph_size, height=glyph_size)
            # The generated glyph already has a viewbox of -50,-50 to 50,50 (100x100)
            # We need to parse its content and add it *inside* glyph_svg_element
            # This is complex without an XML parser.
            # Simpler: Use a group and scale it.
            glyph_group_svg = self.generateGlyph(props, format='svg') # Generate again (cache helps)
            # Need to parse the <g> element out or use svgwrite objects directly
            # Simplification: We know generateGlyph returns <svg><g>...</g></svg>
            # We'll just draw *something* scaled for now. This needs improvement.

            # --- Workaround: Generate glyph directly into a group ---
            map_glyph_group = dwg.g(transform=f"translate({cx}, {cy}) scale({glyph_size / 100})") # Scale from 100x100 base
            # Need to re-implement _generate_svg_glyph slightly to add to existing group
            # or parse the generated string (complex).
            # Let's just add a placeholder circle representing the glyph for now.
            map_glyph_group.add(dwg.circle(center=(0,0), r=40, stroke='black', fill='none'))
            map_glyph_group.add(dwg.text(f"P:{props['polarity']} F:{props['frequency']}", insert=(0,0), text_anchor="middle", font_size="10px"))
            dwg.add(map_glyph_group)


            # Ideal method requires parsing the generated SVG or better integration
            # dwg.add(svgwrite.text.Text(glyph_svg_string)) # This won't render SVG string directly

        try:
            dwg.save()
            print(f"Map saved to {filename}")
            return filename
        except Exception as e:
            print(f"Error saving SVG map: {e}")
            return None


    def invertEntropy(self, props):
        """
        Génère le 'négatif' symbolique d'un glyphe en inversant ses propriétés.
        Fonction expérimentale.
        """
        if not props:
            return None

        inverted_props = props.copy() # Start with a copy
        inverted_props['metrics'] = {} # Don't copy raw metrics, recalculate if needed (not here)
        inverted_props['timestamp'] = time.time()
        inverted_props['text_excerpt'] = f"Inversion de [{props.get('text_excerpt', 'Inconnu')[:20]}...]"

        # Invert Polarity
        if props['polarity'] == '+': inverted_props['polarity'] = '-'
        elif props['polarity'] == '-': inverted_props['polarity'] = '+'
        # 0 and ± remain the same under this simple inversion

        # Invert Frequency (map 1..144 to 144..1)
        inverted_props['frequency'] = 145 - props['frequency']

        # Invert Weight (map 1..10 to 10..1)
        inverted_props['weight'] = 11 - props['weight']

        # Invert Alignment (define opposites)
        align_opposites = {
            'Harmonic': 'Void', #'Discordant' if we add it
            'Chthonic': 'Celestial',
            'Celestial': 'Chthonic',
            'Void': 'Harmonic', # Or maybe Elemental?
            'Elemental': 'Elemental' # Or Void? Elemental feels central
        }
        inverted_props['alignment'] = align_opposites.get(props['alignment'], 'Void') # Default to Void

        print(f"\n--- Inversion d'Entropie pour Glyphe ---")
        print(f"  Original  : P:{props['polarity']} F:{props['frequency']} W:{props['weight']} A:{props['alignment']}")
        print(f"  Inversé   : P:{inverted_props['polarity']} F:{inverted_props['frequency']} W:{inverted_props['weight']} A:{inverted_props['alignment']}")

        return inverted_props

# --- Exécution Principale & Exemple ---

if __name__ == "__main__":
    # Instanciation du miroir
    mirror = SynkrisisVis()

    # Texte exemple
    example_text = "Le monde est un miroir fracturé où l’algorithme apprend à rêver."

    # 1. Analyse du texte exemple
    glyph_properties = mirror.analyzeText(example_text)

    if glyph_properties:
        # 2. Génération du glyphe (ASCII et SVG)
        print("\n--- Génération du Glyphe ---")
        ascii_glyph = mirror.generateGlyph(glyph_properties, format='ascii')
        print("Glyphe ASCII:")
        print(ascii_glyph)

        svg_glyph_string = mirror.generateGlyph(glyph_properties, format='svg')
        if not svg_glyph_string.startswith('['):
            glyph_filename = f"glyph_{glyph_properties['polarity']}_{glyph_properties['frequency']}_{glyph_properties['weight']}_{glyph_properties['alignment']}.svg"
            try:
                with open(glyph_filename, "w", encoding="utf-8") as f:
                    f.write(svg_glyph_string)
                print(f"\nGlyphe SVG sauvegardé dans : {glyph_filename}")
            except Exception as e:
                print(f"\nErreur lors de la sauvegarde du glyphe SVG : {e}")
        else:
            print("\nGlyphe SVG:")
            print(svg_glyph_string) # Print disabled message

        # 3. Inversion d'Entropie (Expérimental)
        inverted_properties = mirror.invertEntropy(glyph_properties)
        if inverted_properties:
            inverted_ascii = mirror.generateGlyph(inverted_properties, format='ascii')
            print("\nGlyphe ASCII Inversé:")
            print(inverted_ascii)

            inverted_svg_string = mirror.generateGlyph(inverted_properties, format='svg')
            if not inverted_svg_string.startswith('['):
                inv_glyph_filename = f"glyph_inverted_{inverted_properties['polarity']}_{inverted_properties['frequency']}_{inverted_properties['weight']}_{inverted_properties['alignment']}.svg"
                try:
                    with open(inv_glyph_filename, "w", encoding="utf-8") as f:
                        f.write(inverted_svg_string)
                    print(f"\nGlyphe SVG Inversé sauvegardé dans : {inv_glyph_filename}")
                except Exception as e:
                    print(f"\nErreur lors de la sauvegarde du glyphe SVG inversé : {e}")

        # 4. Affichage de la carte (avec le glyphe original et inversé)
        print("\n--- Génération de la Carte Fractale ---")
        all_props = [glyph_properties]
        if inverted_properties:
            all_props.append(inverted_properties)

        # Générer quelques glyphes supplémentaires pour la carte
        additional_texts = [
            "Silence vibrant dans le code endormi.",
            "Chaos fractal, écho d'une étoile morte.",
            "Harmonie céleste tissée de lumière pure et d'ombre dansante.",
            " Racine profonde, mémoire de pierre.",
             " ", # Test texte vide
             "Flux et reflux, l'éternel retour élémentaire."
        ]
        for txt in additional_texts:
             props = mirror.analyzeText(txt)
             if props: all_props.append(props)

        map_filename = mirror.displayFractalMap(all_props)
        if map_filename:
             print(f"Carte fractale générée : {map_filename}")
             print("(Note: La visualisation actuelle de la carte est une simplification. L'intégration complète des SVG individuels nécessite une analyse XML ou une refonte de la génération.)")
        else:
             print("Échec de la génération de la carte fractale.")

    else:
        print("L'analyse du texte a échoué.")