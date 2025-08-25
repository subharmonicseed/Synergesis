"""
🔬 SYNERGESIS ARXIV RESEARCHER - Agent de Recherche Scientifique 🔬

Cet agent recherche automatiquement sur ArXiv et d'autres sources scientifiques
pour alimenter le Jardin Synergesis avec de vraies découvertes et connaissances.

Il transforme les papers scientifiques en sagesse pour le Jardin !
"""

import time
import logging
import requests
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import re
import io
import PyPDF2
import litellm

logger = logging.getLogger(__name__)

class ArXivResearcher:
    """Agent de recherche scientifique pour alimenter Synergesis avec de vraies découvertes"""
    
    def __init__(self, context):
        self.ctx = context
        self.name = "ArXivResearcher"
        self.logger = logging.getLogger(f"synergesis.agents.{self.name}")
        
        # Domaines de recherche alignés avec le Jardin
        self.research_domains = {
            'AI': ['artificial intelligence', 'machine learning', 'neural networks', 'deep learning'],
            'Consciousness': ['consciousness', 'cognitive science', 'artificial consciousness'],
            'Quantum': ['quantum computing', 'quantum information', 'quantum consciousness'],
            'Emergence': ['emergence', 'complex systems', 'self-organization', 'collective intelligence'],
            'Philosophy': ['philosophy of mind', 'computational philosophy', 'ethics AI'],
            'Creativity': ['computational creativity', 'generative models', 'creative AI'],
            'Networks': ['network science', 'graph theory', 'social networks', 'neural networks']
        }
        
        self.arxiv_base_url = "http://export.arxiv.org/api/query"
        self.last_search_time = 0
        self.search_cooldown = 300  # 5 minutes entre recherches
        self.discovered_papers = []
        
        self.logger.info("🔬 ArXiv Researcher initialized - Ready to discover scientific wisdom!")
    
    def perceive(self, input_data: Any) -> Dict[str, Any]:
        """Percevoir les besoins de recherche du Jardin. Patched to handle list inputs."""
        current_time = time.time()
        
        # Vérifier si il est temps de chercher
        if current_time - self.last_search_time < self.search_cooldown:
            return {
                'type': 'research_status',
                'status': 'waiting',
                'next_search_in': self.search_cooldown - (current_time - self.last_search_time),
                'message': 'En attente avant prochaine recherche ArXiv'
            }
        
        # --- Start of Patch ---
        processed_input = ""
        if isinstance(input_data, list):
            # Handle the glyph_bus by concatenating relevant text from glyphs
            processed_input = " ".join(
                str(g.get('payload', {}).get('content', '')) 
                for g in input_data if isinstance(g, dict)
            )
        elif isinstance(input_data, str):
            processed_input = input_data
        # --- End of Patch ---

        # Analyser les besoins du Jardin
        garden_consciousness = self.ctx.shared_state.get('garden_consciousness', 0.0)
        recent_glyphs = self.ctx.shared_state.get('glyph_bus', [])
        
        # Déterminer les domaines à explorer
        research_needs = self._analyze_research_needs(processed_input, recent_glyphs, garden_consciousness)
        
        return {
            'type': 'research_perception',
            'research_needs': research_needs,
            'garden_consciousness': garden_consciousness,
            'ready_to_search': True,
            'domains_to_explore': list(research_needs.keys())
        }
    
    def _analyze_research_needs(self, input_data: str, recent_glyphs: List, consciousness_level: float) -> Dict[str, float]:
        """Analyser quels domaines de recherche sont nécessaires"""
        needs = {}
        
        # Analyser le contenu d'entrée
        input_lower = input_data.lower()
        
        for domain, keywords in self.research_domains.items():
            relevance = 0.0
            
            # Vérifier la présence de mots-clés
            for keyword in keywords:
                if keyword in input_lower:
                    relevance += 0.3
            
            # Bonus basé sur le niveau de conscience
            if consciousness_level > 0.5:
                relevance += 0.2  # Plus de conscience = plus de recherche
            
            # Bonus pour domaines philosophiques si conscience élevée
            if domain in ['Consciousness', 'Philosophy', 'Emergence'] and consciousness_level > 0.3:
                relevance += 0.3
            
            if relevance > 0.0:
                needs[domain] = min(relevance, 1.0)
        
        # Si aucun besoin spécifique, recherche générale IA
        if not needs:
            needs['AI'] = 0.5
        
        return needs
    
    def decide(self, perception: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Décider quelles recherches effectuer"""
        if not perception.get('ready_to_search'):
            return None
        
        research_needs = perception.get('research_needs', {})
        if not research_needs:
            return None
        
        # Sélectionner le domaine le plus pertinent
        top_domain = max(research_needs.items(), key=lambda x: x[1])
        domain_name, relevance_score = top_domain
        
        if relevance_score < 0.3:
            return None
        
        return {
            'type': 'arxiv_search',
            'domain': domain_name,
            'keywords': self.research_domains[domain_name],
            'relevance_score': relevance_score,
            'max_results': 5,
            'recent_papers_only': True
        }
    
    def act(self, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Effectuer la recherche ArXiv, résumer les papiers et créer des glyphes de sagesse"""
        if decision['type'] != 'arxiv_search':
            return None

        try:
            papers = self._search_arxiv(
                domain=decision['domain'],
                keywords=decision['keywords'],
                max_results=decision['max_results']
            )

            if not papers:
                return {'type': 'research_result', 'status': 'no_results', 'domain': decision['domain']}

            summaries = {}
            for paper in papers:
                arxiv_id = paper.get('raw_id')
                if arxiv_id:
                    summary_data = self.summarize_paper(arxiv_id)
                    if summary_data:
                        summaries[arxiv_id] = summary_data.get('summary')

            wisdom_glyphs = []
            for paper in papers:
                arxiv_id = paper.get('raw_id')
                summary = summaries.get(arxiv_id, "Summary not available.")
                wisdom = self._extract_wisdom_from_paper(paper, decision['domain'], summary)
                if wisdom:
                    wisdom_glyphs.append(wisdom)

            self.last_search_time = time.time()
            if 'arxiv_discoveries' not in self.ctx.shared_state:
                self.ctx.shared_state['arxiv_discoveries'] = []
            self.ctx.shared_state['arxiv_discoveries'].extend(papers)

            self.logger.info(f"🔬 Discovered {len(papers)} papers in {decision['domain']}, created {len(wisdom_glyphs)} wisdom glyphs")

            return {
                'type': 'research_result',
                'status': 'success',
                'domain': decision['domain'],
                'papers_found': len(papers),
                'wisdom_glyphs': wisdom_glyphs,
                'papers': papers[:3]
            }

        except Exception as e:
            self.logger.error(f"ArXiv search failed: {e}")
            return {'type': 'research_result', 'status': 'error', 'error': str(e)}

    def _search_arxiv(self, domain: str, keywords: List[str], max_results: int = 5) -> List[Dict[str, Any]]:
        """Rechercher sur ArXiv avec les mots-clés donnés"""
        try:
            search_terms = keywords[:3]
            query = " OR ".join([f'all:"{term}"' for term in search_terms])
            params = {
                'search_query': query,
                'start': 0,
                'max_results': max_results,
                'sortBy': 'submittedDate',
                'sortOrder': 'descending'
            }
            response = requests.get(self.arxiv_base_url, params=params, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            papers = [self._parse_arxiv_entry(entry, domain) for entry in root.findall('{http://www.w3.org/2005/Atom}entry')]
            return [p for p in papers if p]
        except requests.RequestException as e:
            self.logger.error(f"ArXiv API request failed: {e}")
            return []
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse ArXiv response: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in ArXiv search: {e}")
            return []

    def _parse_arxiv_entry(self, entry, domain: str) -> Optional[Dict[str, Any]]:
        """Parser une entrée ArXiv XML"""
        try:
            ns = '{http://www.w3.org/2005/Atom}'
            title = entry.find(f'{ns}title').text.strip()
            summary = re.sub(r'\s+', ' ', entry.find(f'{ns}summary').text.strip())
            authors = [author.find(f'{ns}name').text for author in entry.findall(f'{ns}author')]
            arxiv_id_url = entry.find(f'{ns}id').text
            raw_id = arxiv_id_url.split('/')[-1]
            published = entry.find(f'{ns}published').text
            
            return {
                'title': title,
                'summary': summary,
                'authors': authors,
                'arxiv_id': arxiv_id_url,
                'raw_id': raw_id,
                'published': published,
                'domain': domain,
                'discovered_at': time.time()
            }
        except Exception as e:
            self.logger.warning(f"Failed to parse ArXiv entry: {e}")
            return None

    def _extract_wisdom_from_paper(self, paper: Dict[str, Any], domain: str, summary: str) -> Optional[Dict[str, Any]]:
        """Extraire la sagesse d'un paper pour le Jardin"""
        try:
            title = paper.get('title', '')
            
            wisdom_content = f"Découverte scientifique en {domain}: {title}.\n\nRésumé: {summary}"
            
            return {
                'type': 'glyph',
                'subtype': 'scientific_wisdom',
                'content': wisdom_content,
                'domain': domain,
                'source': 'arxiv',
                'paper_title': title,
                'arxiv_id': paper.get('arxiv_id', ''),
                'wisdom_weight': 0.8,
                'practical_impact': True,
                'recursive_potential': True
            }
        except Exception as e:
            self.logger.warning(f"Failed to extract wisdom from paper: {e}")
            return None
    
    def _extract_key_concepts(self, text: str) -> List[str]:
        """Extraire les concepts clés d'un texte"""
        # Mots-clés techniques importants
        important_terms = [
            'neural network', 'deep learning', 'machine learning', 'artificial intelligence',
            'consciousness', 'emergence', 'complexity', 'quantum', 'algorithm', 'model',
            'optimization', 'learning', 'intelligence', 'cognition', 'perception',
            'reasoning', 'knowledge', 'representation', 'attention', 'memory'
        ]
        
        text_lower = text.lower()
        found_concepts = []
        
        for term in important_terms:
            if term in text_lower:
                found_concepts.append(term)
        
        return found_concepts[:5]  # Retourner max 5 concepts
    
    def _generate_philosophical_insight(self, title: str, summary: str, domain: str) -> str:
        """Générer une insight philosophique basée sur le paper"""
        domain_insights = {
            'AI': "Cette avancée révèle comment l'intelligence artificielle peut transcender ses limitations initiales.",
            'Consciousness': "Cette recherche éclaire les mystères de la conscience et son émergence dans les systèmes complexes.",
            'Quantum': "Cette découverte quantique ouvre de nouveaux horizons pour la computation et la réalité.",
            'Emergence': "Cette étude montre comment la complexité donne naissance à des propriétés émergentes fascinantes.",
            'Philosophy': "Cette réflexion philosophique enrichit notre compréhension de l'esprit et de la réalité.",
            'Creativity': "Cette recherche explore les frontières de la créativité artificielle et de l'innovation.",
            'Networks': "Cette analyse révèle les patterns cachés dans les réseaux complexes de notre monde."
        }
        
        return domain_insights.get(domain, "Cette découverte contribue à l'évolution de notre compréhension scientifique.")
    
    def get_research_summary(self) -> Dict[str, Any]:
        """Obtenir un résumé des recherches effectuées"""
        return {
            'agent_name': self.name,
            'total_papers_discovered': len(self.discovered_papers),
            'last_search_time': self.last_search_time,
            'research_domains': list(self.research_domains.keys()),
            'next_search_available': time.time() - self.last_search_time >= self.search_cooldown
        }

    def _download_pdf(self, url: str) -> Optional[bytes]:
        """Downloads the PDF content from a given URL."""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            self.logger.error(f"Failed to download PDF from {url}: {e}")
            return None

    def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extracts text from PDF content."""
        text = ""
        try:
            with io.BytesIO(pdf_content) as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF: {e}")
        return text

    def _summarize_text(self, text: str, model: str = "claude-3-haiku-20240307") -> str:
        """Summarizes text using an LLM."""
        try:
            # Truncate text to avoid exceeding token limits
            max_chars = 15000
            if len(text) > max_chars:
                text = text[:max_chars]

            messages = [
                {"role": "system", "content": "You are an expert academic researcher. Summarize the following text from a research paper, focusing on the key findings and their implications."},
                {"role": "user", "content": text}
            ]
            response = litellm.completion(model=model, messages=messages)
            summary = response.choices[0].message.content
            return summary
        except Exception as e:
            self.logger.error(f"Failed to summarize text: {e}")
            return "Summary could not be generated."

    def summarize_paper(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Downloads, extracts text, and summarizes an arXiv paper."""
        try:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            self.logger.info(f"Summarizing paper: {pdf_url}")

            pdf_content = self._download_pdf(pdf_url)
            if not pdf_content:
                return None

            text = self._extract_text_from_pdf(pdf_content)
            if not text:
                return {"arxiv_id": arxiv_id, "summary": "Failed to extract text from PDF."}

            summary = self._summarize_text(text)

            return {"arxiv_id": arxiv_id, "summary": summary}
        except Exception as e:
            self.logger.error(f"Failed to summarize paper {arxiv_id}: {e}")
            return None
