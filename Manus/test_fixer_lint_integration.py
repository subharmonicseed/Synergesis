#!/usr/bin/env python3
# File: test_fixer_lint_integration.py
# Description: Test script for the integration of GlyphFixer and GlyphLint

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import time

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent))

# Import the modules
try:
    from glyph_fixer_v02 import GlyphFixer, CorrectionLevel, CorrectionReport
    from glyph_lint import validate_glyphs_data, ValidationResult
    import logging
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log_integration = logging.getLogger('fixer_lint_integration')

# Define test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "llm_tests"
RESULTS_DIR = Path(__file__).parent.parent / "llm_tests" / "integration_results"
RESULTS_DIR.mkdir(exist_ok=True)

def load_test_data(filename: str) -> List[Dict[str, Any]]:
    """Load test data from JSON file"""
    try:
        filepath = TEST_DATA_DIR / filename
        if not filepath.exists():
            log_integration.error(f"Test data file not found: {filepath}")
            return []
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            log_integration.error(f"Test data is not a list: {filepath}")
            return []
        
        return data
    except Exception as e:
        log_integration.error(f"Error loading test data from {filename}: {e}")
        return []

def save_results(data: Any, filename: str) -> str:
    """Save results to JSON file"""
    try:
        filepath = RESULTS_DIR / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return str(filepath)
    except Exception as e:
        log_integration.error(f"Error saving results to {filename}: {e}")
        return ""

class IntegrationReport:
    """Report for the integration of GlyphFixer and GlyphLint"""
    def __init__(self):
        self.timestamp = time.time()
        self.input_glyphs_count = 0
        self.fixer_report = None
        self.lint_report = None
        self.fixed_glyphs_count = 0
        self.valid_glyphs_count = 0
        self.invalid_glyphs_count = 0
        self.fixer_corrections_count = 0
        self.fixer_errors_count = 0
        self.lint_errors_count = 0
        self.lint_warnings_count = 0
        self.processing_time = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "timestamp": self.timestamp,
            "input_glyphs_count": self.input_glyphs_count,
            "fixed_glyphs_count": self.fixed_glyphs_count,
            "valid_glyphs_count": self.valid_glyphs_count,
            "invalid_glyphs_count": self.invalid_glyphs_count,
            "fixer_corrections_count": self.fixer_corrections_count,
            "fixer_errors_count": self.fixer_errors_count,
            "lint_errors_count": self.lint_errors_count,
            "lint_warnings_count": self.lint_warnings_count,
            "processing_time": self.processing_time,
            "fixer_report": self.fixer_report,
            "lint_report": self.lint_report
        }
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the report"""
        return (
            f"Integration Report Summary:\n"
            f"- Input Glyphs: {self.input_glyphs_count}\n"
            f"- Fixed Glyphs: {self.fixed_glyphs_count}\n"
            f"- Valid Glyphs: {self.valid_glyphs_count}\n"
            f"- Invalid Glyphs: {self.invalid_glyphs_count}\n"
            f"- Fixer Corrections: {self.fixer_corrections_count}\n"
            f"- Fixer Errors: {self.fixer_errors_count}\n"
            f"- Lint Errors: {self.lint_errors_count}\n"
            f"- Lint Warnings: {self.lint_warnings_count}\n"
            f"- Processing Time: {self.processing_time:.2f} seconds\n"
        )

def process_glyphs(
    input_glyphs: List[Dict[str, Any]],
    correction_level: CorrectionLevel = CorrectionLevel.MODERATE,
    fix_minor_issues: bool = True,
    strict_validation: bool = False
) -> Tuple[List[Dict[str, Any]], IntegrationReport]:
    """
    Process glyphs through the fixer and linter pipeline.
    
    Args:
        input_glyphs: List of input glyphs
        correction_level: Correction level for the fixer
        fix_minor_issues: Whether to fix minor issues in the linter
        strict_validation: Whether to use strict validation
        
    Returns:
        Tuple[List[Dict], IntegrationReport]: (processed_glyphs, integration_report)
    """
    start_time = time.time()
    report = IntegrationReport()
    report.input_glyphs_count = len(input_glyphs)
    
    # Step 1: Run Fixer
    log_integration.info(f"Running GlyphFixer with correction level {correction_level.name}...")
    
    fixer = GlyphFixer(correction_level=correction_level)
    fixed_glyphs, fixer_report = fixer.fix_glyphs_batch(input_glyphs)
    
    report.fixed_glyphs_count = fixer_report.corrected_glyphs
    report.fixer_corrections_count = len(fixer_report.corrections)
    report.fixer_errors_count = len(fixer_report.errors)
    report.fixer_report = fixer_report.to_dict()
    
    log_integration.info(f"GlyphFixer completed. Applied {report.fixer_corrections_count} corrections, encountered {report.fixer_errors_count} unfixed issues.")
    
    # Step 2: Run Linter
    log_integration.info("Running GlyphLint...")
    
    lint_errors, lint_warnings, problematic_glyphs = validate_glyphs_data(
        fixed_glyphs,
        fix_minor_issues=fix_minor_issues,
        strict_errors=strict_validation,
        strict_warnings=False
    )
    
    report.lint_errors_count = lint_errors
    report.lint_warnings_count = lint_warnings
    report.valid_glyphs_count = len(fixed_glyphs) - len([g for g in problematic_glyphs if not g.get('is_valid', True)])
    report.invalid_glyphs_count = len([g for g in problematic_glyphs if not g.get('is_valid', True)])
    report.lint_report = {
        "errors_count": lint_errors,
        "warnings_count": lint_warnings,
        "problematic_glyphs": problematic_glyphs
    }
    
    log_integration.info(f"GlyphLint completed. Found {lint_errors} errors and {lint_warnings} warnings.")
    
    # Finalize report
    end_time = time.time()
    report.processing_time = end_time - start_time
    
    log_integration.info(f"Pipeline processing completed in {report.processing_time:.2f} seconds.")
    log_integration.info(f"Input: {report.input_glyphs_count} glyphs, Valid: {report.valid_glyphs_count} glyphs, Invalid: {report.invalid_glyphs_count} glyphs")
    
    return fixed_glyphs, report

def test_with_problematic_glyphs():
    """Test the integration with problematic glyphs"""
    log_integration.info("=== Testing integration with problematic glyphs ===")
    
    # Load problematic glyphs
    problematic_glyphs = load_test_data("fixer_results/problematic_glyphs_original.json")
    
    if not problematic_glyphs:
        log_integration.error("Failed to load problematic glyphs")
        return
    
    # Test with different correction levels
    for level in CorrectionLevel:
        log_integration.info(f"\n--- Testing with correction level: {level.name} ---")
        
        # Process glyphs
        processed_glyphs, integration_report = process_glyphs(
            problematic_glyphs,
            correction_level=level,
            fix_minor_issues=True,
            strict_validation=False
        )
        
        # Save results
        glyphs_filename = f"problematic_integration_{level.name.lower()}_glyphs.json"
        report_filename = f"problematic_integration_{level.name.lower()}_report.json"
        
        save_results(processed_glyphs, glyphs_filename)
        save_results(integration_report.to_dict(), report_filename)
        
        # Print summary
        print(integration_report.get_summary())

def test_with_llm_output():
    """Test the integration with simulated LLM output"""
    log_integration.info("\n=== Testing integration with simulated LLM output ===")
    
    # Load simulated LLM output
    codepde_glyphs = load_test_data("glyph_output_codepde_v1.2_simulated.json")
    seps_glyphs = load_test_data("glyph_output_seps_v1.2_simulated.json")
    
    if not codepde_glyphs or not seps_glyphs:
        log_integration.error("Failed to load simulated LLM output")
        return
    
    # Test with CodePDE glyphs
    log_integration.info("\n--- Testing with CodePDE glyphs ---")
    
    # Process glyphs
    processed_glyphs, integration_report = process_glyphs(
        codepde_glyphs,
        correction_level=CorrectionLevel.MODERATE,
        fix_minor_issues=True,
        strict_validation=False
    )
    
    # Save results
    glyphs_filename = "codepde_integration_glyphs.json"
    report_filename = "codepde_integration_report.json"
    
    save_results(processed_glyphs, glyphs_filename)
    save_results(integration_report.to_dict(), report_filename)
    
    # Print summary
    print(integration_report.get_summary())
    
    # Test with SEPS glyphs
    log_integration.info("\n--- Testing with SEPS glyphs ---")
    
    # Process glyphs
    processed_glyphs, integration_report = process_glyphs(
        seps_glyphs,
        correction_level=CorrectionLevel.MODERATE,
        fix_minor_issues=True,
        strict_validation=False
    )
    
    # Save results
    glyphs_filename = "seps_integration_glyphs.json"
    report_filename = "seps_integration_report.json"
    
    save_results(processed_glyphs, glyphs_filename)
    save_results(integration_report.to_dict(), report_filename)
    
    # Print summary
    print(integration_report.get_summary())

def main():
    """Main test function"""
    log_integration.info("Starting Fixer-Lint Integration Tests...")
    
    # Test with problematic glyphs
    test_with_problematic_glyphs()
    
    # Test with simulated LLM output
    test_with_llm_output()
    
    log_integration.info("\nAll integration tests completed.")

if __name__ == "__main__":
    main()
