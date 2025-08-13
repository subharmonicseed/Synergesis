# File: glyph_fixer.py
# Version: 0.2
# Description: Synergesis Glyph Corrector - Applies configurable automatic corrections with detailed reporting.

from __future__ import annotations
import json
import time
import logging
import sys
import random
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Union, Set, Callable
from copy import deepcopy  # For safely creating default list/dict values
from enum import Enum, auto

# --- Import from glyph_core ---
try:
    from glyph_core import (
        GlyphData as GlyphDataTyped, GlyphRelationship as GlyphRelationshipTyped,
        SIMPLE_POLARITIES_SET, SIMPLE_ALIGNMENTS_SET, RELATIONSHIP_TYPES_SET, STATUS_VALUES_SET
    )
    SIMPLE_POLARITIES = list(SIMPLE_POLARITIES_SET)
    SIMPLE_ALIGNMENTS = list(SIMPLE_ALIGNMENTS_SET)
    STATUS_VALUES_FIXER = list(STATUS_VALUES_SET)
except ImportError:
    print("WARNING (glyph_fixer): glyph_core.py not found or incomplete. Using fallback constants.", file=sys.stderr)
    # Fallback definitions for standalone understanding
    GlyphData = Dict[str, Any]  # type: ignore
    SIMPLE_POLARITIES = ['+', '-', '0', '±', '?']
    SIMPLE_ALIGNMENTS = ['Celestial', 'Chthonic', 'Void', 'Harmonic', 'Elemental', 'Error', 'Expansion']
    STATUS_VALUES_FIXER = ['raw_from_llm', 'processed_by_fixer', 'validated_by_linter', 'error_fixer']  # Statuses for this stage
    RELATIONSHIP_TYPES_SET = {'ADDRESSES_PROBLEM', 'PROPOSES_SOLUTION_FOR', 'USES_TECHNIQUE', 'IMPLEMENTS_CONCEPT',
                             'EVALUATED_ON_DATASET', 'MEASURED_BY_METRIC', 'RELATED_TO_CONCEPT', 'IMPROVES_ON',
                             'BUILDS_UPON', 'PART_OF_ARCHITECTURE', 'RELATED_TO'}

# --- Logging Setup ---
log_fixer = logging.getLogger('glyph_fixer_v0.2')
if not log_fixer.handlers:
    h_fixer = logging.StreamHandler(sys.stdout)
    h_fixer.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log_fixer.addHandler(h_fixer)
log_fixer.setLevel(logging.INFO)

# --- Constants for Correction ---
# Define default values that are considered SAFE
DEFAULT_STATUS_AFTER_FIX = "processed_by_fixer"
DEFAULT_RELATIONSHIPS: List[Dict[str, Any]] = []
DEFAULT_TAGS: List[str] = []
DEFAULT_NESTED_GLYPHS: List[GlyphData] = []  # type: ignore
DEFAULT_SOURCE_IDS: List[str] = ["unknown_llm_source"]
DEFAULT_ENTROPY = 0.5
DEFAULT_FREQ = 72
DEFAULT_POIDS = 5
DEFAULT_POLARITE = "?"
DEFAULT_ALIGNEMENT = "Void"  # Or "Error" if preferred for uninferrable
DEFAULT_LLM_PROMPT_VERSION = "unknown"
DEFAULT_TIMESTAMP_OFFSET = 0.0  # Default to current time if timestamp is bad

# --- Correction Levels ---
class CorrectionLevel(Enum):
    """
    Defines the aggressiveness level of corrections to apply.
    
    Levels:
    - SAFE: Only apply non-ambiguous corrections (adding missing fields, type conversions)
    - MODERATE: Apply heuristic corrections (clamping values, standardizing tags)
    - AGGRESSIVE: Apply speculative corrections (guessing content, inferring relationships)
    """
    SAFE = auto()
    MODERATE = auto()
    AGGRESSIVE = auto()

# --- Correction Categories ---
class CorrectionCategory(Enum):
    """Categories of corrections for better organization and reporting."""
    MISSING_FIELD = "missing_field"  # Field was missing and added
    TYPE_CONVERSION = "type_conversion"  # Field type was converted
    VALUE_NORMALIZATION = "value_normalization"  # Value was normalized (e.g., clamped)
    STRUCTURE_REPAIR = "structure_repair"  # Structure was repaired (e.g., malformed JSON)
    CONTENT_INFERENCE = "content_inference"  # Content was inferred (e.g., relationships)
    FIELD_REMOVAL = "field_removal"  # Field was removed (e.g., invalid field)

# --- Correction Result ---
class CorrectionResult:
    """Represents the result of a correction operation."""
    def __init__(
        self,
        glyph_id: str,
        field: str,
        category: CorrectionCategory,
        original_value: Any,
        corrected_value: Any,
        reason: str,
        level: CorrectionLevel,
        success: bool = True
    ):
        self.glyph_id = glyph_id
        self.field = field
        self.category = category
        self.original_value = original_value
        self.corrected_value = corrected_value
        self.reason = reason
        self.level = level
        self.success = success
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "glyph_id": self.glyph_id,
            "field": self.field,
            "category": self.category.value,
            "original_value_snippet": str(self.original_value)[:100] if self.original_value is not None else "None",
            "corrected_value_snippet": str(self.corrected_value)[:100] if self.corrected_value is not None else "None",
            "reason": self.reason,
            "level": self.level.name,
            "success": self.success,
            "timestamp": self.timestamp,
            "type": "correction" if self.success else "error_unfixed"
        }

# --- Correction Report ---
class CorrectionReport:
    """Detailed report of corrections applied to glyphs."""
    def __init__(self):
        self.corrections: List[CorrectionResult] = []
        self.errors: List[CorrectionResult] = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.total_glyphs = 0
        self.corrected_glyphs = 0
        self.error_glyphs = 0
    
    def add_correction(self, correction: CorrectionResult):
        """Add a correction to the report."""
        if correction.success:
            self.corrections.append(correction)
        else:
            self.errors.append(correction)
    
    def finalize(self, total_glyphs: int, corrected_glyphs: int, error_glyphs: int):
        """Finalize the report with summary statistics."""
        self.end_time = time.time()
        self.total_glyphs = total_glyphs
        self.corrected_glyphs = corrected_glyphs
        self.error_glyphs = error_glyphs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
            "duration_seconds": self.end_time - self.start_time if self.end_time else 0,
            "total_glyphs": self.total_glyphs,
            "corrected_glyphs": self.corrected_glyphs,
            "error_glyphs": self.error_glyphs,
            "total_corrections": len(self.corrections),
            "total_errors": len(self.errors),
            "corrections_by_category": self._count_by_category(self.corrections),
            "errors_by_category": self._count_by_category(self.errors),
            "corrections_by_level": self._count_by_level(self.corrections),
            "corrections": [c.to_dict() for c in self.corrections],
            "errors": [e.to_dict() for e in self.errors]
        }
    
    def _count_by_category(self, items: List[CorrectionResult]) -> Dict[str, int]:
        """Count items by category."""
        counts = {}
        for item in items:
            category = item.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts
    
    def _count_by_level(self, items: List[CorrectionResult]) -> Dict[str, int]:
        """Count items by correction level."""
        counts = {}
        for item in items:
            level = item.level.name
            counts[level] = counts.get(level, 0) + 1
        return counts
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the report."""
        duration = self.end_time - self.start_time if self.end_time else 0
        return (
            f"Correction Report Summary:\n"
            f"- Duration: {duration:.2f} seconds\n"
            f"- Total Glyphs: {self.total_glyphs}\n"
            f"- Corrected Glyphs: {self.corrected_glyphs}\n"
            f"- Error Glyphs: {self.error_glyphs}\n"
            f"- Total Corrections: {len(self.corrections)}\n"
            f"- Total Errors: {len(self.errors)}\n"
            f"- Corrections by Category: {self._count_by_category(self.corrections)}\n"
            f"- Corrections by Level: {self._count_by_level(self.corrections)}\n"
        )

class GlyphFixer:
    """
    Applies automatic corrections to glyphs with configurable aggressiveness levels.
    
    This class implements the "Fixer Agnostique" approach, where corrections are applied
    based on predefined rules without requiring prior validation from a linter.
    
    Features:
    - Multiple correction levels (SAFE, MODERATE, AGGRESSIVE)
    - Detailed correction reporting
    - Configurable correction strategies
    - Non-destructive operation (original glyphs are not modified)
    """
    def __init__(self, correction_level: CorrectionLevel = CorrectionLevel.SAFE):
        """
        Initialize the GlyphFixer with a specified correction level.
        
        Args:
            correction_level: The aggressiveness level of corrections to apply.
                              Defaults to SAFE.
        """
        self.correction_level = correction_level
        self.report = CorrectionReport()
        
        # Define correction strategies by level
        self.correction_strategies = {
            CorrectionLevel.SAFE: self._get_safe_strategies(),
            CorrectionLevel.MODERATE: self._get_moderate_strategies(),
            CorrectionLevel.AGGRESSIVE: self._get_aggressive_strategies()
        }
    
    def _get_safe_strategies(self) -> List[Callable[[Dict[str, Any], str], Dict[str, Any]]]:
        """Get the list of SAFE correction strategies."""
        return [
            self._ensure_required_fields,
            self._convert_numeric_fields,
            self._serialize_details_json,
            self._validate_relationships
        ]
    
    def _get_moderate_strategies(self) -> List[Callable[[Dict[str, Any], str], Dict[str, Any]]]:
        """Get the list of MODERATE correction strategies (includes SAFE)."""
        return self._get_safe_strategies() + [
            self._clamp_numeric_values,
            self._standardize_polarite_alignement,
            self._normalize_tags
        ]
    
    def _get_aggressive_strategies(self) -> List[Callable[[Dict[str, Any], str], Dict[str, Any]]]:
        """Get the list of AGGRESSIVE correction strategies (includes MODERATE)."""
        return self._get_moderate_strategies() + [
            self._infer_missing_details_json,
            self._infer_relationships_from_tags,
            self._guess_concept_type_from_content
        ]
    
    def _log_correction(
        self,
        glyph_id: str,
        field: str,
        category: CorrectionCategory,
        original_value: Any,
        corrected_value: Any,
        reason: str,
        level: CorrectionLevel
    ):
        """Log a successful correction."""
        correction = CorrectionResult(
            glyph_id=glyph_id,
            field=field,
            category=category,
            original_value=original_value,
            corrected_value=corrected_value,
            reason=reason,
            level=level,
            success=True
        )
        self.report.add_correction(correction)
        log_fixer.debug(f"FIX: Glyph '{glyph_id}', Field '{field}': {reason}. From '{str(original_value)[:30]}' to '{str(corrected_value)[:30]}'")
    
    def _log_error(
        self,
        glyph_id: str,
        field: str,
        category: CorrectionCategory,
        value: Any,
        reason: str,
        level: CorrectionLevel
    ):
        """Log an error that couldn't be fixed."""
        error = CorrectionResult(
            glyph_id=glyph_id,
            field=field,
            category=category,
            original_value=value,
            corrected_value=None,
            reason=reason,
            level=level,
            success=False
        )
        self.report.add_correction(error)
        log_fixer.warning(f"FIXER_ERROR: Glyph '{glyph_id}', Field '{field}': {reason}. Value: '{str(value)[:50]}'")
    
    # --- Correction Strategies ---
    
    def _ensure_required_fields(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Ensure all required fields are present with valid default values."""
        fixed_glyph = deepcopy(glyph)
        
        # Ensure ID exists
        if "id" not in fixed_glyph:
            fixed_glyph["id"] = gid
            self._log_correction(
                gid, "id", CorrectionCategory.MISSING_FIELD,
                None, gid, "Generated missing ID",
                CorrectionLevel.SAFE
            )
        
        # Ensure list fields
        for field, default_factory in [
            ("relationships", lambda: list(DEFAULT_RELATIONSHIPS)),
            ("tags", lambda: list(DEFAULT_TAGS)),
            ("sourceIds", lambda: list(DEFAULT_SOURCE_IDS)),
            ("nested_glyphs", lambda: list(DEFAULT_NESTED_GLYPHS))
        ]:
            if field not in fixed_glyph or fixed_glyph[field] is None:
                fixed_glyph[field] = default_factory()
                self._log_correction(
                    gid, field, CorrectionCategory.MISSING_FIELD,
                    glyph.get(field), fixed_glyph[field],
                    "Field missing or None, added default empty list",
                    CorrectionLevel.SAFE
                )
            elif not isinstance(fixed_glyph[field], list):
                original_val = fixed_glyph[field]
                # Attempt to make it a list if it's a single item
                if isinstance(original_val, (str, int, float, dict, tuple)):
                    fixed_glyph[field] = [original_val]
                    self._log_correction(
                        gid, field, CorrectionCategory.TYPE_CONVERSION,
                        original_val, fixed_glyph[field],
                        "Converted non-list to list of one item",
                        CorrectionLevel.SAFE
                    )
                else:
                    self._log_error(
                        gid, field, CorrectionCategory.TYPE_CONVERSION,
                        original_val,
                        f"Expected list, got {type(original_val).__name__}. Left as is for linter.",
                        CorrectionLevel.SAFE
                    )
        
        # Ensure core symbolic properties
        for field, default_value in [
            ("polarité", DEFAULT_POLARITE),
            ("alignement", DEFAULT_ALIGNEMENT),
            ("fréquence", DEFAULT_FREQ),
            ("poids", DEFAULT_POIDS),
            ("entropy_score", DEFAULT_ENTROPY),
            ("status", DEFAULT_STATUS_AFTER_FIX),
            ("llm_prompt_version", DEFAULT_LLM_PROMPT_VERSION),
            ("timestamp", time.time())
        ]:
            if field not in fixed_glyph or fixed_glyph[field] is None:
                fixed_glyph[field] = default_value
                self._log_correction(
                    gid, field, CorrectionCategory.MISSING_FIELD,
                    glyph.get(field), fixed_glyph[field],
                    f"Field missing or None, added default: {default_value}",
                    CorrectionLevel.SAFE
                )
        
        return fixed_glyph
    
    def _convert_numeric_fields(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Convert string numeric fields to their appropriate types."""
        fixed_glyph = deepcopy(glyph)
        
        for field_key, type_func in [
            ("fréquence", int), ("poids", int),
            ("entropy_score", float), ("timestamp", float),
            ("resonance", float), ("emergence", int)
        ]:
            original_value = fixed_glyph.get(field_key)
            if isinstance(original_value, str):
                try:
                    converted_value = type_func(original_value)
                    fixed_glyph[field_key] = converted_value
                    self._log_correction(
                        gid, field_key, CorrectionCategory.TYPE_CONVERSION,
                        original_value, converted_value,
                        f"Converted string to {type_func.__name__}",
                        CorrectionLevel.SAFE
                    )
                except (ValueError, TypeError):
                    self._log_error(
                        gid, field_key, CorrectionCategory.TYPE_CONVERSION,
                        original_value,
                        f"String value not convertible to {type_func.__name__}. Left for linter.",
                        CorrectionLevel.SAFE
                    )
        
        return fixed_glyph
    
    def _serialize_details_json(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Serialize details_json if it's a Python dict."""
        fixed_glyph = deepcopy(glyph)
        
        details_val = fixed_glyph.get("details_json")
        if isinstance(details_val, dict):
            try:
                fixed_glyph["details_json"] = json.dumps(details_val)
                self._log_correction(
                    gid, "details_json", CorrectionCategory.TYPE_CONVERSION,
                    "Python dict object", "Serialized JSON string",
                    "Serialized dict to JSON string",
                    CorrectionLevel.SAFE
                )
            except TypeError:
                self._log_error(
                    gid, "details_json", CorrectionCategory.TYPE_CONVERSION,
                    "Python dict object",
                    "Dict not JSON serializable. Left for linter.",
                    CorrectionLevel.SAFE
                )
        elif details_val is not None and not isinstance(details_val, str):
            self._log_error(
                gid, "details_json", CorrectionCategory.TYPE_CONVERSION,
                details_val,
                f"Expected string or dict, got {type(details_val).__name__}. Left for linter.",
                CorrectionLevel.SAFE
            )
        
        return fixed_glyph
    
    def _validate_relationships(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Validate and fix relationship structures."""
        fixed_glyph = deepcopy(glyph)
        
        if isinstance(fixed_glyph.get("relationships"), list):
            valid_relationships = []
            for i, rel in enumerate(fixed_glyph["relationships"]):
                if isinstance(rel, dict) and "type" in rel and "target_glyph_id" in rel:
                    valid_relationships.append(rel)
                else:
                    self._log_error(
                        gid, f"relationships[{i}]", CorrectionCategory.STRUCTURE_REPAIR,
                        rel,
                        "Malformed relationship object (missing type or target_glyph_id). Discarded.",
                        CorrectionLevel.SAFE
                    )
            
            if len(valid_relationships) != len(fixed_glyph["relationships"]):
                self._log_correction(
                    gid, "relationships", CorrectionCategory.STRUCTURE_REPAIR,
                    fixed_glyph["relationships"], valid_relationships,
                    "Removed malformed relationship objects",
                    CorrectionLevel.SAFE
                )
                fixed_glyph["relationships"] = valid_relationships
        
        return fixed_glyph
    
    def _clamp_numeric_values(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Clamp numeric values to valid ranges (MODERATE level)."""
        if self.correction_level.value < CorrectionLevel.MODERATE.value:
            return glyph
        
        fixed_glyph = deepcopy(glyph)
        
        # Define valid ranges for numeric fields
        valid_ranges = {
            "fréquence": (1, 144),
            "poids": (1, 10),
            "entropy_score": (0.0, 1.0),
            "resonance": (0.0, 1.0)
        }
        
        for field, (min_val, max_val) in valid_ranges.items():
            if field in fixed_glyph and isinstance(fixed_glyph[field], (int, float)):
                original_value = fixed_glyph[field]
                
                if original_value < min_val:
                    fixed_glyph[field] = min_val
                    self._log_correction(
                        gid, field, CorrectionCategory.VALUE_NORMALIZATION,
                        original_value, min_val,
                        f"Clamped value to minimum ({min_val})",
                        CorrectionLevel.MODERATE
                    )
                elif original_value > max_val:
                    fixed_glyph[field] = max_val
                    self._log_correction(
                        gid, field, CorrectionCategory.VALUE_NORMALIZATION,
                        original_value, max_val,
                        f"Clamped value to maximum ({max_val})",
                        CorrectionLevel.MODERATE
                    )
        
        return fixed_glyph
    
    def _standardize_polarite_alignement(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Standardize polarité and alignement values (MODERATE level)."""
        if self.correction_level.value < CorrectionLevel.MODERATE.value:
            return glyph
        
        fixed_glyph = deepcopy(glyph)
        
        # Standardize polarité
        if "polarité" in fixed_glyph:
            original_polarite = fixed_glyph["polarité"]
            
            if isinstance(original_polarite, str) and original_polarite not in SIMPLE_POLARITIES:
                # Try to map to a valid polarité
                polarite_map = {
                    "positive": "+", "negative": "-", "neutral": "0",
                    "ambivalent": "±", "unknown": "?", "plus": "+", "minus": "-",
                    "zero": "0", "null": "0", "ambiguous": "±", "uncertain": "?"
                }
                
                normalized = polarite_map.get(original_polarite.lower())
                if normalized:
                    fixed_glyph["polarité"] = normalized
                    self._log_correction(
                        gid, "polarité", CorrectionCategory.VALUE_NORMALIZATION,
                        original_polarite, normalized,
                        f"Standardized polarité value to {normalized}",
                        CorrectionLevel.MODERATE
                    )
                else:
                    self._log_error(
                        gid, "polarité", CorrectionCategory.VALUE_NORMALIZATION,
                        original_polarite,
                        f"Unknown polarité value, cannot standardize. Left for linter.",
                        CorrectionLevel.MODERATE
                    )
        
        # Standardize alignement
        if "alignement" in fixed_glyph:
            original_alignement = fixed_glyph["alignement"]
            
            if isinstance(original_alignement, str) and original_alignement not in SIMPLE_ALIGNMENTS:
                # Try to map to a valid alignement
                alignement_map = {
                    "celestial": "Celestial", "chthonic": "Chthonic", "void": "Void",
                    "harmonic": "Harmonic", "elemental": "Elemental", "error": "Error",
                    "expansion": "Expansion", "unknown": "Void", "neutral": "Void"
                }
                
                normalized = alignement_map.get(original_alignement.lower())
                if normalized:
                    fixed_glyph["alignement"] = normalized
                    self._log_correction(
                        gid, "alignement", CorrectionCategory.VALUE_NORMALIZATION,
                        original_alignement, normalized,
                        f"Standardized alignement value to {normalized}",
                        CorrectionLevel.MODERATE
                    )
                else:
                    self._log_error(
                        gid, "alignement", CorrectionCategory.VALUE_NORMALIZATION,
                        original_alignement,
                        f"Unknown alignement value, cannot standardize. Left for linter.",
                        CorrectionLevel.MODERATE
                    )
        
        return fixed_glyph
    
    def _normalize_tags(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Normalize tags (MODERATE level)."""
        if self.correction_level.value < CorrectionLevel.MODERATE.value:
            return glyph
        
        fixed_glyph = deepcopy(glyph)
        
        if "tags" in fixed_glyph and isinstance(fixed_glyph["tags"], list):
            original_tags = fixed_glyph["tags"]
            normalized_tags = []
            
            # Define concept types for validation
            concept_types = {
                "Problem", "TechnicalConcept", "ProposedSolution", "KeyContribution",
                "Methodology", "Dataset", "Metric", "ToolFramework",
                "TheoreticalPrinciple", "ArchitecturalPattern"
            }
            
            # Define tag normalization map
            tag_map = {
                "problem": "Problem", "technical concept": "TechnicalConcept",
                "proposed solution": "ProposedSolution", "key contribution": "KeyContribution",
                "methodology": "Methodology", "dataset": "Dataset",
                "metric": "Metric", "tool framework": "ToolFramework",
                "theoretical principle": "TheoreticalPrinciple",
                "architectural pattern": "ArchitecturalPattern",
                
                # Domain-specific normalizations
                "machine learning": "machine_learning", "deep learning": "deep_learning",
                "reinforcement learning": "reinforcement_learning",
                "neural network": "neural_networks", "neural networks": "neural_networks",
                "natural language processing": "natural_language_processing",
                "computer vision": "computer_vision", "nlp": "natural_language_processing",
                "cv": "computer_vision", "ml": "machine_learning", "dl": "deep_learning",
                "rl": "reinforcement_learning", "nn": "neural_networks"
            }
            
            for tag in original_tags:
                if isinstance(tag, str):
                    # Check if it's already a valid concept type
                    if tag in concept_types:
                        normalized_tags.append(tag)
                        continue
                    
                    # Try to normalize
                    normalized = tag_map.get(tag.lower())
                    if normalized:
                        normalized_tags.append(normalized)
                    else:
                        # Keep original if no normalization found
                        normalized_tags.append(tag)
                else:
                    self._log_error(
                        gid, "tags", CorrectionCategory.TYPE_CONVERSION,
                        tag,
                        f"Tag is not a string. Skipped.",
                        CorrectionLevel.MODERATE
                    )
            
            # Remove duplicates while preserving order
            seen = set()
            unique_tags = []
            for tag in normalized_tags:
                if tag not in seen:
                    seen.add(tag)
                    unique_tags.append(tag)
            
            if unique_tags != original_tags:
                fixed_glyph["tags"] = unique_tags
                self._log_correction(
                    gid, "tags", CorrectionCategory.VALUE_NORMALIZATION,
                    original_tags, unique_tags,
                    "Normalized and deduplicated tags",
                    CorrectionLevel.MODERATE
                )
        
        return fixed_glyph
    
    def _infer_missing_details_json(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Infer missing details_json from other fields (AGGRESSIVE level)."""
        if self.correction_level.value < CorrectionLevel.AGGRESSIVE.value:
            return glyph
        
        fixed_glyph = deepcopy(glyph)
        
        # Only proceed if details_json is missing or empty
        if "details_json" not in fixed_glyph or not fixed_glyph["details_json"]:
            # Try to infer from tags and natural_prompt
            tags = fixed_glyph.get("tags", [])
            natural_prompt = fixed_glyph.get("natural_prompt", "")
            
            # Find concept type
            concept_type = next((tag for tag in tags if tag in {
                "Problem", "TechnicalConcept", "ProposedSolution", "KeyContribution",
                "Methodology", "Dataset", "Metric", "ToolFramework",
                "TheoreticalPrinciple", "ArchitecturalPattern"
            }), None)
            
            if concept_type and natural_prompt:
                # Create a basic details_json based on concept type
                details = {}
                
                if concept_type == "Problem":
                    details = {
                        "problem_statement": natural_prompt,
                        "affected_components": [tag for tag in tags if tag != concept_type]
                    }
                elif concept_type == "TechnicalConcept":
                    details = {
                        "concept_name": gid,
                        "definition": natural_prompt,
                        "key_properties": [tag for tag in tags if tag != concept_type]
                    }
                elif concept_type == "ProposedSolution":
                    details = {
                        "solution_name": gid,
                        "summary": natural_prompt,
                        "key_mechanisms_or_components": [tag for tag in tags if tag != concept_type]
                    }
                # Add more concept types as needed
                
                if details:
                    fixed_glyph["details_json"] = json.dumps(details)
                    self._log_correction(
                        gid, "details_json", CorrectionCategory.CONTENT_INFERENCE,
                        None, fixed_glyph["details_json"],
                        f"Inferred details_json from concept_type {concept_type} and natural_prompt",
                        CorrectionLevel.AGGRESSIVE
                    )
        
        return fixed_glyph
    
    def _infer_relationships_from_tags(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Infer relationships from tags (AGGRESSIVE level)."""
        # This is a placeholder for the actual implementation
        # In a real implementation, this would analyze tags and infer relationships
        # based on domain knowledge
        return glyph
    
    def _guess_concept_type_from_content(self, glyph: Dict[str, Any], gid: str) -> Dict[str, Any]:
        """Guess concept type from content (AGGRESSIVE level)."""
        # This is a placeholder for the actual implementation
        # In a real implementation, this would analyze the content and guess
        # the concept type based on keywords and patterns
        return glyph
    
    def fix_single_glyph(self, raw_glyph_dict: Dict[str, Any]) -> GlyphData:
        """
        Apply corrections to a single glyph dictionary.
        
        Args:
            raw_glyph_dict: The raw glyph dictionary to fix
            
        Returns:
            GlyphData: The fixed glyph dictionary
        """
        # Generate a glyph ID if not present
        gid = str(raw_glyph_dict.get("id", f"fixer_genid_{random.randint(1000, 9999)}"))
        
        # Apply all correction strategies for the current level
        fixed_glyph = raw_glyph_dict
        for strategy in self.correction_strategies[self.correction_level]:
            try:
                fixed_glyph = strategy(fixed_glyph, gid)
            except Exception as e:
                self._log_error(
                    gid, "strategy_execution", CorrectionCategory.STRUCTURE_REPAIR,
                    str(e),
                    f"Error executing correction strategy {strategy.__name__}: {e}",
                    self.correction_level
                )
        
        return fixed_glyph  # type: ignore
    
    def fix_glyphs_batch(
        self,
        raw_glyph_list: List[Dict[str, Any]],
        correction_level: Optional[CorrectionLevel] = None
    ) -> Tuple[List[GlyphData], CorrectionReport]:
        """
        Apply corrections to a batch of glyph dictionaries.
        
        Args:
            raw_glyph_list: The list of raw glyph dictionaries to fix
            correction_level: Optional override for the correction level
            
        Returns:
            Tuple[List[GlyphData], CorrectionReport]: The fixed glyphs and the correction report
        """
        # Reset report for this batch
        self.report = CorrectionReport()
        
        # Use provided correction level or instance default
        current_level = correction_level or self.correction_level
        
        # Initialize result list
        fixed_glyphs_list: List[GlyphData] = []
        corrected_glyphs = 0
        error_glyphs = 0
        
        # Validate input
        if not isinstance(raw_glyph_list, list):
            log_fixer.critical("Input to fix_glyphs_batch is not a list. Aborting.")
            self._log_error(
                "BATCH_LEVEL", "raw_glyph_list", CorrectionCategory.TYPE_CONVERSION,
                type(raw_glyph_list).__name__,
                "Input must be a list of glyphs.",
                current_level
            )
            
            self.report.finalize(0, 0, 0)
            return [], self.report
        
        # Process each glyph
        for i, glyph_dict in enumerate(raw_glyph_list):
            if not isinstance(glyph_dict, dict):
                log_fixer.error(f"Skipping non-dictionary item at index {i} in glyph list: {type(glyph_dict)}")
                self._log_error(
                    f"item_at_index_{i}", "glyph_object", CorrectionCategory.TYPE_CONVERSION,
                    str(glyph_dict)[:100],
                    "Item is not a dictionary.",
                    current_level
                )
                error_glyphs += 1
                continue
            
            try:
                # Save the original correction level
                original_level = self.correction_level
                
                # Set the current correction level
                self.correction_level = current_level
                
                # Fix the glyph
                fixed_glyph = self.fix_single_glyph(glyph_dict)
                fixed_glyphs_list.append(fixed_glyph)
                
                # Restore the original correction level
                self.correction_level = original_level
                
                # Count corrected glyphs
                if len([c for c in self.report.corrections if c.glyph_id == fixed_glyph.get("id")]) > 0:
                    corrected_glyphs += 1
            except Exception as e:
                # Catch any unexpected error during individual glyph fixing
                gid_err = str(glyph_dict.get("id", f"UNKNOWN_ID_AT_INDEX_{i}"))
                self._log_error(
                    gid_err, "fix_single_glyph_call", CorrectionCategory.STRUCTURE_REPAIR,
                    str(e)[:200],
                    f"Unexpected error during fixing: {e}",
                    current_level
                )
                
                # Add the original glyph back, unfixed
                fixed_glyphs_list.append(deepcopy(glyph_dict))  # type: ignore
                error_glyphs += 1
        
        # Finalize report
        self.report.finalize(len(raw_glyph_list), corrected_glyphs, error_glyphs)
        
        log_fixer.info(
            f"Fixer batch run completed. Inspected {len(raw_glyph_list)} glyphs. "
            f"Applied {len(self.report.corrections)} corrections. "
            f"Encountered {len(self.report.errors)} unfixed issues (logged)."
        )
        
        return fixed_glyphs_list, self.report

# --- Utility Functions ---

def generate_report_id() -> str:
    """Generate a unique report ID."""
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)
    return f"fixer_report_{timestamp}_{random_suffix}"

def save_correction_report(report: CorrectionReport, output_dir: str) -> str:
    """
    Save a correction report to a file.
    
    Args:
        report: The correction report to save
        output_dir: The directory to save the report to
        
    Returns:
        str: The path to the saved report
    """
    import os
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate report ID and filename
    report_id = generate_report_id()
    filename = f"{report_id}.json"
    filepath = os.path.join(output_dir, filename)
    
    # Save report to file
    with open(filepath, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    
    return filepath

# --- Test Function ---

def test_fixer():
    """Test the GlyphFixer with sample data."""
    # Sample glyphs with various issues
    sample_glyphs = [
        {
            # Missing fields
            "id": "test_glyph_1",
            "polarité": "+",
            "alignement": "Void",
            "tags": ["TechnicalConcept", "machine learning"]
        },
        {
            # Type conversion issues
            "id": "test_glyph_2",
            "polarité": "+",
            "alignement": "Void",
            "fréquence": "80",  # String instead of int
            "poids": "5",  # String instead of int
            "tags": ["Problem", "nlp"],
            "details_json": {"key": "value"}  # Dict instead of string
        },
        {
            # Value normalization issues
            "id": "test_glyph_3",
            "polarité": "positive",  # Non-standard value
            "alignement": "celestial",  # Non-standard value
            "fréquence": 200,  # Out of range
            "poids": 15,  # Out of range
            "tags": ["ProposedSolution", "neural network", "neural networks"],  # Duplicates
            "entropy_score": 1.5  # Out of range
        },
        {
            # Relationship issues
            "id": "test_glyph_4",
            "polarité": "+",
            "alignement": "Void",
            "fréquence": 80,
            "poids": 5,
            "tags": ["KeyContribution", "machine_learning"],
            "relationships": [
                {"type": "IMPLEMENTS_CONCEPT"},  # Missing target_glyph_id
                {"target_glyph_id": "test_glyph_1"}  # Missing type
            ]
        }
    ]
    
    # Test with different correction levels
    for level in CorrectionLevel:
        print(f"\n=== Testing with correction level: {level.name} ===")
        
        fixer = GlyphFixer(correction_level=level)
        fixed_glyphs, report = fixer.fix_glyphs_batch(sample_glyphs)
        
        print(f"Fixed {report.corrected_glyphs} out of {report.total_glyphs} glyphs")
        print(f"Applied {len(report.corrections)} corrections")
        print(f"Encountered {len(report.errors)} unfixed issues")
        
        # Print summary by category
        print("\nCorrections by category:")
        for category, count in report._count_by_category(report.corrections).items():
            print(f"  {category}: {count}")
        
        # Print sample corrections
        print("\nSample corrections:")
        for correction in report.corrections[:5]:
            print(f"  {correction.field}: {correction.reason}")
    
    return fixed_glyphs, report

if __name__ == "__main__":
    test_fixer()
