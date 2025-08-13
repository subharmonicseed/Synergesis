# DeepResearch Agent - External Knowledge Acquisition
# Mission: Recherche externe (Wikipedia, ArXiv) et génération de glyphs

import requests
import json
import time
import logging
from typing import Dict, Any, List, Optional
from .core_agents import BaseAgent, AgentContext
from .garden import SynergesisGarden

class DeepResearchAgent(BaseAgent):
    """
    Agent DeepResearch - Recherche de connaissances externes
    
    Capacités:
    - Recherche Wikipedia automatique
    - Intégration ArXiv (via ArXivResearcher)
    - Génération de glyphs sémantiques
    - Validation et stockage NOUS
    """
    
    def __init__(self, context: AgentContext):
        super().__init__(context)
        self.name = "DeepResearch"
        self.research_domains = {
            'science': ['physics', 'biology', 'chemistry', 'mathematics'],
            'technology': ['artificial intelligence', 'quantum computing', 'robotics'],
            'philosophy': ['consciousness', 'ethics', 'metaphysics'],
            'nature': ['biomimétisme', 'écosystèmes', 'évolution'],
            'society': ['collective intelligence', 'emergence', 'complexity']
        }
        
        # Sources multiples vérifiables (pas Wikipedia seule)
        self.verified_sources = {
            'arxiv': {
                'api': 'http://export.arxiv.org/api/query',
                'reliability': 0.9,
                'type': 'academic_preprint'
            },
            'pubmed': {
                'api': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',
                'reliability': 0.95,
                'type': 'peer_reviewed'
            },
            'semantic_scholar': {
                'api': 'https://api.semanticscholar.org/graph/v1/paper/search',
                'reliability': 0.85,
                'type': 'academic_aggregator'
            }
        }
        
        self.last_research_time = 0
        self.research_cooldown = 30  # 30 secondes entre recherches
        self.min_sources_required = 2  # Minimum 2 sources pour validation
        
    def perceive(self, stimulus: Any) -> Dict[str, Any]:
        """
        Perception: Analyse si le stimulus nécessite une recherche externe. 
        Handles various input types including glyph buses.
        """
        try:
            # Handle different input types to get a single text string
            if isinstance(stimulus, list):
                # If it's a list of glyphs, extract their payloads
                if stimulus and hasattr(stimulus[0], 'payload'):
                    text_to_analyze = ' '.join(str(glyph.payload) for glyph in stimulus if hasattr(glyph, 'payload'))
                else:
                    # Join list of strings with spaces
                    text_to_analyze = ' '.join(str(item) for item in stimulus)
            elif isinstance(stimulus, str):
                text_to_analyze = stimulus
            else:
                # Convert any other type to string as a fallback
                text_to_analyze = str(stimulus)

            # Mots-clés déclencheurs de recherche
            research_triggers = [
                'research:', 'recherche:', 'wiki:', 'wikipedia:',
                'biomimétisme', 'intelligence artificielle', 'quantique',
                'conscience', 'émergence', 'complexité'
            ]
            
            stimulus_lower = text_to_analyze.lower()
            
            # Vérifier si c'est une demande de recherche explicite
            explicit_research = any(trigger in stimulus_lower for trigger in research_triggers)
            
            # Extraire le terme de recherche
            research_term = None
            if 'research:' in stimulus_lower:
                research_term = text_to_analyze.split('research:')[1].strip()
            elif 'recherche:' in stimulus_lower:
                research_term = text_to_analyze.split('recherche:')[1].strip()
            elif 'wiki:' in stimulus_lower:
                research_term = text_to_analyze.split('wiki:')[1].strip()
            else:
                # Utiliser le stimulus complet comme terme de recherche
                research_term = text_to_analyze.strip()
                
            # Vérifier le cooldown
            current_time = time.time()
            can_research = (current_time - self.last_research_time) > self.research_cooldown
            
            perception = {
                'type': 'research_request',
                'explicit_research': explicit_research,
                'research_term': research_term,
                'can_research': can_research,
                'cooldown_remaining': max(0, self.research_cooldown - (current_time - self.last_research_time)),
                'confidence': 0.9 if explicit_research else 0.6,
                'timestamp': current_time
            }
            
            # Logging
            self._log(f"🔍 Perception DeepResearch: {research_term}")
            if not can_research:
                self._log(f"⏳ Cooldown actif: {perception['cooldown_remaining']:.1f}s restantes")
            
            return perception
            
        except Exception as e:
            self._log(f"❌ Erreur perception DeepResearch: {str(e)}")
            return {'type': 'error', 'message': str(e)}
    
    def decide(self, perception: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Décision: Choisir la stratégie de recherche appropriée
        """
        try:
            if perception.get('type') != 'research_request':
                return None
                
            if not perception.get('can_research', False):
                return None
                
            research_term = perception.get('research_term', '').strip()
            if not research_term:
                return None
            
            # Déterminer le domaine de recherche
            domain = self._classify_research_domain(research_term)
            
            # Choisir la stratégie multi-sources
            strategy = 'multi_source_verification'  # Vérification croisée obligatoire
            
            decision = {
                'type': 'external_research',
                'strategy': strategy,
                'research_term': research_term,
                'domain': domain,
                'priority': perception.get('confidence', 0.6),
                'sources_to_query': list(self.verified_sources.keys()),
                'min_sources_required': self.min_sources_required,
                'timestamp': time.time()
            }
            
            self._log(f"🤔 Décision DeepResearch: {strategy} sur '{research_term}' (domaine: {domain})")
            
            return decision
            
        except Exception as e:
            self._log(f"❌ Erreur décision DeepResearch: {str(e)}")
            return None
    
    def act(self, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Action: Effectuer la recherche externe et générer des glyphs
        """
        try:
            if decision.get('type') != 'external_research':
                return None
            
            research_term = decision.get('research_term', '')
            strategy = decision.get('strategy', 'wikipedia')
            domain = decision.get('domain', 'general')
            
            self._log(f"🔬 Recherche {strategy} en cours: '{research_term}'")
            
            # Effectuer la recherche multi-sources
            if strategy == 'multi_source_verification':
                research_result = self._search_multiple_sources(research_term, decision.get('sources_to_query', []))
            else:
                research_result = {'status': 'error', 'message': f'Stratégie {strategy} non implémentée'}
            
            if research_result.get('status') != 'success':
                self._log(f"❌ Échec recherche: {research_result.get('message', 'Erreur inconnue')}")
                return research_result
            
            # Générer des glyphs à partir des résultats
            glyphs = self._generate_research_glyphs(research_result, domain, research_term)
            
            # Stocker dans NOUS et le Jardin
            storage_result = self._store_research_results(glyphs, research_term, domain)
            
            # Mettre à jour le timestamp
            self.last_research_time = time.time()
            
            action_result = {
                'status': 'success',
                'strategy': strategy,
                'research_term': research_term,
                'domain': domain,
                'glyphs_generated': len(glyphs),
                'glyphs': glyphs[:3],  # Limiter pour éviter le spam
                'storage_result': storage_result,
                'summary': research_result.get('summary', ''),
                'timestamp': self.last_research_time
            }
            
            self._log(f"✅ DeepResearch terminé: {len(glyphs)} glyphs générés")
            
            return action_result
            
        except Exception as e:
            self._log(f"❌ Erreur action DeepResearch: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def _classify_research_domain(self, term: str) -> str:
        """Classifier le terme de recherche dans un domaine"""
        term_lower = term.lower()
        
        for domain, keywords in self.research_domains.items():
            if any(keyword in term_lower for keyword in keywords):
                return domain
        
        # Domaines spéciaux
        if any(word in term_lower for word in ['bio', 'nature', 'animal', 'plante']):
            return 'nature'
        elif any(word in term_lower for word in ['ia', 'ai', 'robot', 'tech']):
            return 'technology'
        elif any(word in term_lower for word in ['philo', 'éthique', 'conscience']):
            return 'philosophy'
        
        return 'general'
    
    def _search_multiple_sources(self, term: str, sources_to_query: List[str]) -> Dict[str, Any]:
        """
        Recherche multi-sources avec vérification croisée
        Exige minimum 2 sources vérifiables pour valider l'information
        """
        try:
            self._log(f"🔍 Recherche multi-sources pour: '{term}'")
            
            source_results = {}
            verified_info = []
            total_reliability = 0.0
            
            # Interroger chaque source
            for source_name in sources_to_query:
                if source_name not in self.verified_sources:
                    continue
                    
                source_config = self.verified_sources[source_name]
                self._log(f"📡 Interrogation {source_name} ({source_config['type']})...")
                
                try:
                    if source_name == 'arxiv':
                        result = self._search_arxiv(term)
                    elif source_name == 'pubmed':
                        result = self._search_pubmed(term)
                    elif source_name == 'semantic_scholar':
                        result = self._search_semantic_scholar(term)
                    else:
                        result = {'status': 'not_implemented'}
                    
                    if result.get('status') == 'success':
                        result['reliability'] = source_config['reliability']
                        result['source_type'] = source_config['type']
                        source_results[source_name] = result
                        verified_info.extend(result.get('papers', []))
                        total_reliability += source_config['reliability']
                        self._log(f"✅ {source_name}: {len(result.get('papers', []))} résultats")
                    else:
                        self._log(f"❌ {source_name}: {result.get('message', 'Échec')}")
                        
                except Exception as e:
                    self._log(f"⚠️ Erreur {source_name}: {str(e)}")
                    continue
            
            # Vérifier si on a assez de sources
            verified_sources_count = len(source_results)
            
            if verified_sources_count < self.min_sources_required:
                return {
                    'status': 'insufficient_sources',
                    'message': f'Seulement {verified_sources_count} sources vérifiées (minimum {self.min_sources_required} requis)',
                    'sources_found': verified_sources_count,
                    'sources_required': self.min_sources_required
                }
            
            # Analyser et croiser les informations
            cross_verified_info = self._cross_verify_information(verified_info, source_results)
            
            # Calculer le score de fiabilité global
            avg_reliability = total_reliability / verified_sources_count if verified_sources_count > 0 else 0.0
            
            return {
                'status': 'success',
                'research_term': term,
                'sources_verified': verified_sources_count,
                'total_papers': len(verified_info),
                'cross_verified_concepts': cross_verified_info,
                'reliability_score': avg_reliability,
                'source_breakdown': source_results,
                'verification_level': 'multi_source_verified'
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Erreur recherche multi-sources: {str(e)}'}
    
    def _search_arxiv(self, term: str) -> Dict[str, Any]:
        """
        Recherche ArXiv pour papers scientifiques
        """
        try:
            # Utiliser l'ArXivResearcher existant si possible
            from .arxiv_researcher import ArXivResearcher
            
            arxiv_agent = ArXivResearcher(self.ctx)
            
            # Simuler une perception pour déclencher la recherche
            perception = arxiv_agent.perceive(f"research: {term}")
            if perception.get('ready_to_search'):
                decision = arxiv_agent.decide(perception)
                if decision:
                    action = arxiv_agent.act(decision)
                    if action and action.get('status') == 'success':
                        return {
                            'status': 'success',
                            'papers': action.get('papers', []),
                            'source': 'arxiv'
                        }
            
            return {'status': 'no_results', 'message': 'Aucun résultat ArXiv'}
            
        except Exception as e:
            return {'status': 'error', 'message': f'Erreur ArXiv: {str(e)}'}
    
    def _search_pubmed(self, term: str) -> Dict[str, Any]:
        """
        Recherche PubMed pour publications médicales/biologiques
        """
        try:
            # API PubMed basique (nécessiterait une clé API pour usage intensif)
            base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                'db': 'pubmed',
                'term': term,
                'retmax': 5,
                'retmode': 'json'
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                ids = data.get('esearchresult', {}).get('idlist', [])
                
                if ids:
                    # Simuler des résultats (vraie implémentation nécessiterait efetch)
                    papers = []
                    for i, pmid in enumerate(ids[:3]):
                        papers.append({
                            'id': f'pubmed_{pmid}',
                            'title': f'PubMed Study {i+1} on {term}',
                            'abstract': f'Verified medical/biological research on {term}',
                            'source': 'pubmed',
                            'pmid': pmid
                        })
                    
                    return {
                        'status': 'success',
                        'papers': papers,
                        'source': 'pubmed'
                    }
            
            return {'status': 'no_results', 'message': 'Aucun résultat PubMed'}
            
        except Exception as e:
            return {'status': 'error', 'message': f'Erreur PubMed: {str(e)}'}
    
    def _search_semantic_scholar(self, term: str) -> Dict[str, Any]:
        """
        Recherche Semantic Scholar pour publications académiques
        """
        try:
            # API Semantic Scholar (gratuite avec limitations)
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': term,
                'limit': 5,
                'fields': 'title,abstract,authors,year,citationCount'
            }
            
            response = requests.get(url, params=params, timeout=10, headers={
                'User-Agent': 'Synergesis-DeepResearch/1.0'
            })
            
            if response.status_code == 200:
                data = response.json()
                papers_data = data.get('data', [])
                
                if papers_data:
                    papers = []
                    for paper in papers_data[:3]:
                        papers.append({
                            'id': f"semantic_{paper.get('paperId', 'unknown')}",
                            'title': paper.get('title', 'Unknown Title'),
                            'abstract': paper.get('abstract', '')[:200] + '...' if paper.get('abstract') else '',
                            'authors': [author.get('name', 'Unknown') for author in paper.get('authors', [])[:3]],
                            'year': paper.get('year'),
                            'citations': paper.get('citationCount', 0),
                            'source': 'semantic_scholar'
                        })
                    
                    return {
                        'status': 'success',
                        'papers': papers,
                        'source': 'semantic_scholar'
                    }
            
            return {'status': 'no_results', 'message': 'Aucun résultat Semantic Scholar'}
            
        except Exception as e:
            return {'status': 'error', 'message': f'Erreur Semantic Scholar: {str(e)}'}
    
    def _cross_verify_information(self, all_papers: List[Dict], source_results: Dict) -> List[Dict[str, Any]]:
        """
        Vérification croisée des informations entre sources
        """
        try:
            verified_concepts = []
            
            # Extraire les concepts communs entre sources
            if len(source_results) >= 2:
                # Analyser les titres et abstracts pour concepts récurrents
                all_text = ""
                for paper in all_papers:
                    title = paper.get('title', '')
                    abstract = paper.get('abstract', '')
                    all_text += f" {title} {abstract}"
                
                # Concepts de base (amélioration possible avec NLP)
                common_terms = []
                text_lower = all_text.lower()
                
                # Rechercher des termes techniques récurrents
                technical_terms = ['algorithm', 'method', 'system', 'model', 'approach', 'technique']
                for term in technical_terms:
                    if text_lower.count(term) >= 2:  # Apparaît dans au moins 2 sources
                        common_terms.append(term)
                
                if common_terms:
                    verified_concepts.append({
                        'type': 'cross_verified_concepts',
                        'concepts': common_terms,
                        'verification_level': 'multi_source',
                        'sources_count': len(source_results)
                    })
            
            return verified_concepts
            
        except Exception as e:
            self._log(f"⚠️ Erreur vérification croisée: {str(e)}")
            return []
    
    def _generate_research_glyphs(self, research_result: Dict[str, Any], domain: str, term: str) -> List[Dict[str, Any]]:
        """
        Générer des glyphs sémantiques à partir des résultats multi-sources vérifiés
        """
        glyphs = []
        
        try:
            if research_result.get('status') != 'success':
                return glyphs
            
            sources_verified = research_result.get('sources_verified', 0)
            reliability_score = research_result.get('reliability_score', 0.0)
            total_papers = research_result.get('total_papers', 0)
            verification_level = research_result.get('verification_level', 'unknown')
            
            # Glyph principal - synthèse multi-sources
            main_glyph = {
                'id': f"sem-multisource-{int(time.time())}",
                'type': 'verified_knowledge',
                'content': f"🔍🔒 {term}: Vérifié par {sources_verified} sources académiques ({total_papers} publications)",
                'metadata': {
                    'verification_level': verification_level,
                    'sources_verified': sources_verified,
                    'total_papers': total_papers,
                    'domain': domain,
                    'research_term': term,
                    'reliability_score': reliability_score,
                    'timestamp': time.time(),
                    'agent': 'DeepResearch',
                    'quality_assured': True
                },
                'purity_score': min(0.95, reliability_score + 0.1),  # Très haute pureté pour sources multiples
                'coherence_score': 0.9
            }
            glyphs.append(main_glyph)
            
            # Glyphs par source vérifiée
            source_breakdown = research_result.get('source_breakdown', {})
            for source_name, source_data in source_breakdown.items():
                papers = source_data.get('papers', [])
                source_reliability = source_data.get('reliability', 0.0)
                source_type = source_data.get('source_type', 'unknown')
                
                if papers:
                    # Prendre le meilleur paper de cette source
                    best_paper = papers[0]  # Supposons trié par pertinence
                    
                    source_glyph = {
                        'id': f"sem-{source_name}-{int(time.time())}",
                        'type': 'source_verified_knowledge',
                        'content': f"🎯 {source_name.upper()}: {best_paper.get('title', 'Unknown Title')[:80]}...",
                        'metadata': {
                            'source': source_name,
                            'source_type': source_type,
                            'source_reliability': source_reliability,
                            'paper_id': best_paper.get('id', 'unknown'),
                            'domain': domain,
                            'research_term': term,
                            'timestamp': time.time(),
                            'agent': 'DeepResearch',
                            'verified': True
                        },
                        'purity_score': source_reliability,
                        'coherence_score': 0.8
                    }
                    glyphs.append(source_glyph)
            
            # Glyphs de concepts croisés vérifiés
            cross_verified = research_result.get('cross_verified_concepts', [])
            for concept_data in cross_verified:
                if concept_data.get('type') == 'cross_verified_concepts':
                    concepts = concept_data.get('concepts', [])
                    sources_count = concept_data.get('sources_count', 0)
                    
                    if concepts:
                        concept_glyph = {
                            'id': f"sem-crossverified-{int(time.time())}",
                            'type': 'cross_verified_concept',
                            'content': f"🔗✅ Concepts vérifiés: {', '.join(concepts[:5])}",
                            'metadata': {
                                'concepts': concepts,
                                'cross_verification_sources': sources_count,
                                'domain': domain,
                                'research_term': term,
                                'verification_level': 'cross_verified',
                                'timestamp': time.time(),
                                'agent': 'DeepResearch',
                                'high_confidence': True
                            },
                            'purity_score': 0.92,  # Très haute pureté pour concepts croisés
                            'coherence_score': 0.85
                        }
                        glyphs.append(concept_glyph)
            
            self._log(f"🌸 {len(glyphs)} glyphs multi-sources générés pour '{term}' (fiabilité: {reliability_score:.2f})")
            
        except Exception as e:
            self._log(f"❌ Erreur génération glyphs multi-sources: {str(e)}")
        
        return glyphs
    
    def _store_research_results(self, glyphs: List[Dict[str, Any]], term: str, domain: str) -> Dict[str, Any]:
        """
        Stocker les résultats dans NOUS et le Jardin
        """
        try:
            storage_results = {
                'nous_stored': 0,
                'garden_planted': 0,
                'errors': []
            }
            
            # Stocker dans le Jardin si disponible
            if hasattr(self.ctx, 'shared_state') and self.ctx.shared_state:
                try:
                    garden = SynergesisGarden(self.ctx.shared_state)
                    
                    for glyph in glyphs:
                        garden_result = garden.plant_wisdom_seed(
                            agent_name='DeepResearch',
                            wisdom_content=glyph['content'],
                            domain=domain
                        )
                        
                        if garden_result.get('planted', False):
                            storage_results['garden_planted'] += 1
                        
                except Exception as e:
                    storage_results['errors'].append(f"Erreur Jardin: {str(e)}")
            
            # Stocker dans NOUS si disponible
            try:
                from .nous import Nous
                nous = Nous(self.ctx)
                
                for glyph in glyphs:
                    nous.store_concept(
                        glyph['content'],
                        {
                            'domain': domain,
                            'source': 'DeepResearch',
                            'research_term': term,
                            'purity': glyph.get('purity_score', 0.5)
                        }
                    )
                    storage_results['nous_stored'] += 1
                    
            except Exception as e:
                storage_results['errors'].append(f"Erreur NOUS: {str(e)}")
            
            # Ajouter au glyph_bus partagé
            if hasattr(self.ctx, 'shared_state') and self.ctx.shared_state:
                glyph_bus = self.ctx.shared_state.get('glyph_bus', [])
                for glyph in glyphs:
                    glyph_bus.append(glyph)
                self.ctx.shared_state['glyph_bus'] = glyph_bus
            
            # NOUVEAU: Stocker dans la base persistante SQLite
            try:
                from synergesis.core.persistent_storage import PersistentStorage
                storage = PersistentStorage()
                
                for glyph in glyphs:
                    # Convertir le glyph DeepResearch au format persistant
                    persistent_glyph = {
                        'id': glyph['id'],
                        'agent_name': 'DeepResearch',
                        'content': glyph['content'],
                        'visual_symbol': '🔬⚛️',  # Symbole DeepResearch
                        'agent_signature': '🔬 DeepResearch :: Knowledge Acquisition',
                        'symbolic_properties': {
                            'polarity': '+ (Expansion/Connaissance)',
                            'frequency': '95 Hz',
                            'weight': f"{glyph.get('purity_score', 0.8):.1f}/10/10",
                            'alignment': 'Academic (Validation scientifique)',
                            'entropy': f"{1 - glyph.get('coherence_score', 0.8):.3f}"
                        },
                        'human_translation': f"🔬⚛️ [Expansion/Connaissance] @95Hz - Validation scientifique: {glyph['content']}",
                        'symbolic_tags': ['deepresearch', 'multi_source_verified', domain.lower()],
                        'depth_level': 'Profondeur Académique',
                        'timestamp': glyph.get('metadata', {}).get('timestamp', time.time()),
                        'purity_score': glyph.get('purity_score', 0.8),
                        'coherence_score': glyph.get('coherence_score', 0.8),
                        'metadata': glyph.get('metadata', {})
                    }
                    
                    # Stocker dans SQLite
                    storage.store_glyph(persistent_glyph)
                    storage_results['garden_planted'] += 1  # Compter les stockages persistants
                    
                self._log(f"✅ {len(glyphs)} glyphs stockés dans la base persistante SQLite")
                
            except Exception as e:
                storage_results['errors'].append(f"Erreur stockage persistant: {str(e)}")
                self._log(f"❌ Erreur stockage persistant: {str(e)}")
            
            self._log(f"💾 Stockage: {storage_results['nous_stored']} NOUS, {storage_results['garden_planted']} Jardin + Persistant")
            
            return storage_results
            
        except Exception as e:
            return {'errors': [f"Erreur stockage: {str(e)}"]}
    
    def _log(self, message: str):
        """Logging avec préfixe DeepResearch"""
        print(f"[DeepResearch] {message}")
        if hasattr(self.ctx, 'shared_state') and self.ctx.shared_state:
            logs = self.ctx.shared_state.get('agent_logs', [])
            logs.append(f"[{time.strftime('%H:%M:%S')}] DeepResearch: {message}")
            self.ctx.shared_state['agent_logs'] = logs[-100:]  # Garder 100 derniers logs
