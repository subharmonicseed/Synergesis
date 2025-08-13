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