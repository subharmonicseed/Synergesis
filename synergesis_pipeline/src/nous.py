import os
from datetime import datetime
from typing import Optional, List

from sqlmodel import Field, SQLModel
from whoosh.fields import ID, TEXT, SchemaClass

from glyph_bus import GlyphBus


class Concept(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    concept_id: str = Field(index=True, unique=True)
    natural_prompt: str
    concept_type: str
    source: str
    timestamp: float = Field(default_factory=datetime.now().timestamp)
    resonance: Optional[float] = None
    weight: Optional[float] = None


class Nous:
    def __init__(self, db_path: str = "nous.db", index_dir: str = "nous_index"):
        self.db_path = db_path
        self.index_dir = index_dir
        self.bus = GlyphBus()
        self._init_db()
        self._init_search_index()

    def _init_db(self):
        from sqlmodel import create_engine
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        SQLModel.metadata.create_all(self.engine)

    def _init_search_index(self):
        from whoosh.index import create_in, open_dir
        from whoosh.fields import Schema, ID, TEXT
        
        class ConceptSchema(SchemaClass):
            concept_id = ID(stored=True, unique=True)
            natural_prompt = TEXT(stored=True)
            concept_type = TEXT(stored=True)
            source = TEXT(stored=True)

        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)
            self.index = create_in(self.index_dir, ConceptSchema)
        else:
            self.index = open_dir(self.index_dir)

    def add_concept(self, concept: Concept) -> Concept:
        from sqlmodel import Session, select
        with Session(self.engine) as session:
            existing_concept = session.exec(select(Concept).where(Concept.concept_id == concept.concept_id)).first()
            if existing_concept:
                # Update existing concept
                existing_concept.natural_prompt = concept.natural_prompt
                existing_concept.concept_type = concept.concept_type
                existing_concept.source = concept.source
                existing_concept.resonance = concept.resonance
                existing_concept.weight = concept.weight
                session.add(existing_concept)
                session.commit()
                session.refresh(existing_concept)
                self.bus.publish("concept_changed", existing_concept.dict())
                return existing_concept
            else:
                # Add new concept
                session.add(concept)
                session.commit()
                session.refresh(concept)
                self._add_to_index(concept)
                self.bus.publish("new_candidate_concept", concept.dict())
                return concept

    def get_concept_by_id(self, concept_id: str) -> Optional[Concept]:
        from sqlmodel import Session, select
        with Session(self.engine) as session:
            return session.exec(select(Concept).where(Concept.concept_id == concept_id)).first()

    def get_all_concepts(self) -> List[Concept]:
        from sqlmodel import Session, select
        with Session(self.engine) as session:
            return session.exec(select(Concept)).all()

    def query_concepts(self, query_string: str) -> List[Concept]:
        from whoosh.qparser import QueryParser
        from whoosh.index import open_dir
        from sqlmodel import Session, select

        results = []
        with self.index.searcher() as searcher:
            parser = QueryParser("natural_prompt", schema=self.index.schema)
            query = parser.parse(query_string)
            for hit in searcher.search(query):
                concept_id = hit["concept_id"]
                concept = self.get_concept_by_id(concept_id)
                if concept:
                    results.append(concept)
        return results

    def update_concept(self, concept: Concept) -> Concept:
        from sqlmodel import Session
        with Session(self.engine) as session:
            session.add(concept)
            session.commit()
            session.refresh(concept)
            self._update_index(concept)
            self.bus.publish("concept_changed", concept.dict())
            return concept

    def delete_concept(self, concept_id: str):
        from sqlmodel import Session, select
        with Session(self.engine) as session:
            concept = session.exec(select(Concept).where(Concept.concept_id == concept_id)).first()
            if concept:
                session.delete(concept)
                session.commit()
                self._delete_from_index(concept_id)
                self.bus.publish("concept_changed", {"concept_id": concept_id, "status": "deleted"})

    def _add_to_index(self, concept: Concept):
        writer = self.index.writer()
        writer.add_document(
            concept_id=concept.concept_id,
            natural_prompt=concept.natural_prompt,
            concept_type=concept.concept_type,
            source=concept.source
        )
        writer.commit()

    def _update_index(self, concept: Concept):
        writer = self.index.writer()
        writer.update_document(
            concept_id=concept.concept_id,
            natural_prompt=concept.natural_prompt,
            concept_type=concept.concept_type,
            source=concept.source
        )
        writer.commit()

    def _delete_from_index(self, concept_id: str):
        writer = self.index.writer()
        writer.delete_by_term("concept_id", concept_id)
        writer.commit()


if __name__ == "__main__":
    # Exemple d'utilisation
    nous = Nous()

    # Ajouter des concepts
    concept1 = Concept(concept_id="concept_A", natural_prompt="Ceci est le concept A", concept_type="TYPE1", source="Source1", resonance=0.8, weight=0.7)
    nous.add_concept(concept1)

    concept2 = Concept(concept_id="concept_B", natural_prompt="Ceci est le concept B", concept_type="TYPE2", source="Source2", resonance=0.5, weight=0.9)
    nous.add_concept(concept2)

    # Récupérer un concept
    retrieved_concept = nous.get_concept_by_id("concept_A")
    print(f"Concept récupéré: {retrieved_concept}")

    # Rechercher des concepts
    search_results = nous.query_concepts("concept A")
    print(f"Résultats de recherche: {search_results}")

    # Mettre à jour un concept
    concept1.natural_prompt = "Ceci est le concept A mis à jour"
    updated_concept = nous.update_concept(concept1)
    print(f"Concept mis à jour: {updated_concept}")

    # Supprimer un concept
    nous.delete_concept("concept_B")
    print("Concept B supprimé.")

    # Vérifier que le concept B n'existe plus
    retrieved_concept_b = nous.get_concept_by_id("concept_B")
    print(f"Concept B après suppression: {retrieved_concept_b}")


