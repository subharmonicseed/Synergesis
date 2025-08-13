"""
Glyph Lint - Validation and quality control for Glyph objects

This module provides validation and quality control functions for Glyph objects
before they are stored in Neo4j. It ensures data integrity and consistency.
"""

from typing import List, Dict
from pydantic import BaseModel, Field, ValidationError
from ingestion.glyphifier import Glyph
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GlyphValidator:
    """Validator for Glyph objects"""
    
    def validate_glyph(self, glyph: Glyph) -> bool:
        """
        Validate a single Glyph object
        
        Args:
            glyph (Glyph): Glyph object to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Re-validate using Pydantic
            Glyph(**glyph.dict())
            
            # Additional custom validations
            if not glyph.id:
                raise ValueError("Glyph ID cannot be empty")
            
            if not glyph.source:
                raise ValueError("Source cannot be empty")
            
            if not glyph.concept_type:
                raise ValueError("Concept type cannot be empty")
            
            if not glyph.content:
                raise ValueError("Content cannot be empty")
            
            logger.info(f"Glyph {glyph.id} validated successfully")
            return True
            
        except ValidationError as e:
            logger.error(f"Validation error for glyph {glyph.id}: {str(e)}")
            return False
        except ValueError as e:
            logger.error(f"Value error for glyph {glyph.id}: {str(e)}")
            return False
    
    def validate_batch(self, glyphs: List[Glyph]) -> Dict[str, bool]:
        """
        Validate a batch of Glyph objects
        
        Args:
            glyphs (List[Glyph]): List of Glyph objects to validate
            
        Returns:
            Dict[str, bool]: Dictionary mapping glyph IDs to validation status
        """
        results = {}
        for glyph in glyphs:
            results[glyph.id] = self.validate_glyph(glyph)
        return results
    
    def get_validation_report(self, glyphs: List[Glyph]) -> Dict:
        """
        Generate a detailed validation report for a batch of Glyphs
        
        Args:
            glyphs (List[Glyph]): List of Glyph objects to analyze
            
        Returns:
            Dict: Validation report containing statistics and issues
        """
        report = {
            "total_glyphs": len(glyphs),
            "valid_glyphs": 0,
            "invalid_glyphs": 0,
            "validation_issues": []
        }
        
        for glyph in glyphs:
            if self.validate_glyph(glyph):
                report["valid_glyphs"] += 1
            else:
                report["invalid_glyphs"] += 1
                report["validation_issues"].append({
                    "glyph_id": glyph.id,
                    "issues": self._get_validation_issues(glyph)
                })
        
        return report
    
    def _get_validation_issues(self, glyph: Glyph) -> List[str]:
        """Get specific validation issues for a glyph"""
        issues = []
        try:
            Glyph(**glyph.dict())
        except ValidationError as e:
            issues.extend([str(err) for err in e.errors()])
        
        return issues
