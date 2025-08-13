import json
import os
import networkx as nx
import glob

# Configuration
INPUT_DIR_GLYPHIFIED = "/home/ubuntu/synergesis_pipeline/data/arxiv_cs_ai/glyphified/"

def load_glyph_data(file_path):
    """Charge les données de glyphes à partir d'un fichier JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Erreur de chargement du fichier {file_path}: {e}")
        return None

def build_glyph_graph(glyph_data_list):
    """
    Construit un graphe NetworkX à partir d'une liste de données de glyphes.
    Chaque élément de glyph_data_list est une liste de glyphes pour un document.
    """
    graph = nx.DiGraph()
    all_glyphs_flat = [glyph for doc_glyphs in glyph_data_list for glyph in doc_glyphs]

    for glyph in all_glyphs_flat:
        node_id = glyph.get("id")
        if not node_id:
            continue
        
        # Ajouter le nœud glyphe avec ses attributs
        # On stocke tout l'objet glyphe comme attribut du nœud pour un accès facile
        graph.add_node(node_id, **glyph)

    # Ajouter les relations après que tous les nœuds sont ajoutés
    for glyph in all_glyphs_flat:
        source_node_id = glyph.get("id")
        if not source_node_id or not graph.has_node(source_node_id):
            continue

        relationships = glyph.get("relationships", [])
        for rel in relationships:
            target_node_id = rel.get("target_glyph_id")
            rel_type = rel.get("type")
            if target_node_id and rel_type and graph.has_node(target_node_id):
                graph.add_edge(source_node_id, target_node_id, type=rel_type)
            else:
                print(f"  Avertissement: Cible de relation '{target_node_id}' non trouvée ou type manquant pour le glyphe '{source_node_id}'.")
    return graph

# Fonctions de requête exemple
def get_glyphs_for_document(graph, document_id):
    """Récupère tous les glyphes associés à un ID de document source."""
    doc_glyphs = []
    for node, data in graph.nodes(data=True):
        if data.get("source_document_id") == document_id:
            doc_glyphs.append(data)
    return doc_glyphs

def find_method_results_pairs(graph):
    """Trouve les paires de glyphes (Méthode, Résultat) liées par ACHIEVED_BY_METHOD."""
    pairs = []
    for u, v, data in graph.edges(data=True):
        if data.get("type") == "ACHIEVED_BY_METHOD":
            source_node_data = graph.nodes[u]
            target_node_data = graph.nodes[v]
            # L'arête va de Résultat -> Méthode (selon la simulation)
            # Donc u est le résultat, v est la méthode
            if source_node_data.get("details_type") == "ResultContribution" and target_node_data.get("details_type") == "Method":
                pairs.append({
                    "result_glyph": source_node_data.get("natural_prompt"), 
                    "method_glyph": target_node_data.get("natural_prompt")
                })
    return pairs

def find_glyphs_by_tag(graph, tag):
    """Trouve les glyphes contenant un tag spécifique."""
    tagged_glyphs = []
    for node, data in graph.nodes(data=True):
        if tag.lower() in [t.lower() for t in data.get("tags", [])]:
            tagged_glyphs.append(data.get("natural_prompt"))
    return tagged_glyphs

if __name__ == "__main__":
    print("Début de l'exploration du graphe de glyphes simulés...")

    glyph_files = glob.glob(os.path.join(INPUT_DIR_GLYPHIFIED, "*_glyphs.json"))
    
    if not glyph_files:
        print(f"Aucun fichier de glyphes trouvé dans {INPUT_DIR_GLYPHIFIED}")
        exit()

    # Charger les données des 5 premiers fichiers pour cet exemple
    sample_glyph_files = glyph_files[:5]
    all_sample_glyphs_data = []
    print(f"Chargement des données de glyphes depuis {len(sample_glyph_files)} fichiers...")
    for g_file in sample_glyph_files:
        data = load_glyph_data(g_file)
        if data:
            all_sample_glyphs_data.append(data)
    
    if not all_sample_glyphs_data:
        print("Aucune donnée de glyphe n'a pu être chargée.")
        exit()

    print("Construction du graphe de glyphes...")
    glyph_graph = build_glyph_graph(all_sample_glyphs_data)
    print(f"Graphe construit avec {glyph_graph.number_of_nodes()} nœuds et {glyph_graph.number_of_edges()} arêtes.")

    print("\n--- Exemples de Requêtes ---")

    # 1. Afficher les glyphes pour le premier document traité
    if all_sample_glyphs_data and all_sample_glyphs_data[0]:
        first_doc_id = all_sample_glyphs_data[0][0].get("source_document_id") # Prend le premier glyphe du premier doc
        if first_doc_id:
            print(f"\nGlyphes pour le document '{first_doc_id}':")
            doc_glyphs_found = get_glyphs_for_document(glyph_graph, first_doc_id)
            for i, g_data in enumerate(doc_glyphs_found):
                print(f"  {i+1}. ID: {g_data.get('id')}, Type: {g_data.get('details_type')}, Prompt: {g_data.get('natural_prompt')[:80]}...")
        else:
            print("Impossible de récupérer l'ID du premier document pour la requête.")
    
    # 2. Trouver les paires Méthode-Résultat
    print("\nPaires Méthode-Résultat trouvées:")
    method_result_pairs = find_method_results_pairs(glyph_graph)
    if method_result_pairs:
        for i, pair in enumerate(method_result_pairs):
            print(f"  {i+1}. Résultat: {pair['result_glyph'][:60]}... -> Méthode: {pair['method_glyph'][:60]}...")
    else:
        print("  Aucune paire Méthode-Résultat trouvée avec la relation 'ACHIEVED_BY_METHOD'.")

    # 3. Trouver les glyphes avec le tag "sota"
    search_tag = "sota"
    print(f"\nGlyphes avec le tag '{search_tag}':")
    sota_glyphs = find_glyphs_by_tag(glyph_graph, search_tag)
    if sota_glyphs:
        for i, prompt in enumerate(sota_glyphs):
            print(f"  {i+1}. {prompt[:100]}...")
    else:
        print(f"  Aucun glyphe trouvé avec le tag '{search_tag}'.")

    print("\nExploration du graphe de glyphes simulés terminée.")

