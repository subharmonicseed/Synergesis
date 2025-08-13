### **SYNLGLYPH Project: Sprint 3 Kick-off**
**Status:** Active
**Date:** July 17, 2025

---

### **1.0 Introduction**

This document officially marks the commencement of **Sprint 3: Concept Model Enhancement Implementation**. The planning and preparation phases are complete. The primary objective for this sprint is to successfully implement, test, and integrate the `weight` and `resonance` features into the `Concept` Pydantic model and the associated `nous_service` processing pipeline.

The following sections provide a granular breakdown of all technical tasks required to meet the sprint goal.

---

### **2.0 Task Breakdown: Feature Implementation (Story-611)**

**User Story:** As a Developer, I want to implement comprehensive unit tests for the new `_calculate_weight` and `_calculate_resonance` methods to ensure their logic is correct and handles edge cases.

This story covers the core development of the new features and the associated unit tests.

| Task ID | Task Description | Key Actions & Implementation Notes |
| :--- | :--- | :--- |
| **1.1** | **Update Pydantic Model in `schemas.py`** | Modify the `Concept` model in `app/api/v1/schemas.py`. Add the optional `weight` and `resonance` fields with Pydantic `Field` validation to enforce their respective value constraints (`[0.0, 1.0]` for weight and `[-1.0, 1.0]` for resonance). |
| **1.2** | **Implement `_calculate_weight()` Logic** | In `app/services/semantic_processor.py`, implement the `_calculate_weight` function. The logic must use a logistic function based on word count, calibrated to meet the criteria specified in test cases `TC-COR-01`, `TC-COR-02`, and `TC-COR-03`. |
| **1.3** | **Implement `_calculate_resonance()` Logic** | In `app/services/semantic_processor.py`, implement the `_calculate_resonance` function. The logic must be based on keyword matching from a predefined set of positive and negative terms, ensuring it correctly handles scenarios with positive-only, negative-only, mixed, and neutral content as per `TC-COR-04` through `TC-COR-07`. |
| **1.4** | **Write Unit Tests for Calculation Functions** | Create a new unit test file. Write focused tests that directly invoke the `_calculate_weight` and `_calculate_resonance` functions with controlled inputs. Verify their return values against expected outputs, covering all correctness and edge case scenarios (`TC-COR-*` & `TC-EDG-*`) at the function level. |

---

### **3.0 Task Breakdown: Integration Testing (Story-612)**

**User Story:** As a QA Engineer, I want to enhance the `Selene` integration test suite to validate that the new `weight` and `resonance` fields are correctly populated and propagated through the end-to-end pipeline.

This story involves implementing the full integration test suite using the pre-defined stubs in `test_concept_enhancements.py`.

| Task ID | Test Function to Implement | Key Actions & Implementation Notes |
| :--- | :--- | :--- |
| **2.1** | `test_weight_calculation_for_short_text` | Pass a short text (~20 words) to the service and assert that the resulting `weight` is low (< 0.2). |
| **2.2** | `test_weight_calculation_for_medium_text` | Pass a medium text (~50 words) and assert the `weight` is approximately 0.5. |
| **2.3** | `test_weight_calculation_for_long_text` | Pass a long text (~150 words) and assert the `weight` approaches 1.0 (> 0.9). |
| **2.4** | `test_resonance_calculation_for_positive_keywords` | Pass text containing only positive keywords and assert the `resonance` is exactly 1.0. |
| **2.5** | `test_resonance_calculation_for_negative_keywords` | Pass text containing only negative keywords and assert the `resonance` is exactly -1.0. |
| **2.6** | `test_resonance_calculation_for_mixed_keywords` | Pass text with an equal count of positive and negative keywords and assert `resonance` is 0.0. |
| **2.7** | `test_resonance_calculation_for_neutral_text` | Pass text with no relevant keywords and assert the `resonance` is 0.0. |
| **2.8** | `test_end_to_end_pipeline_flow` | Implement a full pipeline test: publish an `AnalysisRequest` to the `documents.pending` topic, consume the resulting `Concept` message from `concepts.completed`, and assert that the `weight` and `resonance` fields are present, valid, and within their schema constraints. |
| **2.9** | `test_processing_of_empty_string_input` | Pass a message with `text: ""` and verify the service does not crash, calculating a valid `weight` and a `resonance` of 0.0. |
| **2.10**| `test_processing_of_whitespace_and_punctuation_only` | Pass a message with `text: "  .?! "` and verify the service does not crash, returning a valid `weight` and a `resonance` of 0.0. |
| **2.11**| `test_pydantic_model_weight_upper_bound_validation` | Finalize the test to confirm that instantiating a `Concept` with `weight > 1.0` raises a `pydantic.ValidationError`. |
| **2.12**| `test_pydantic_model_resonance_lower_bound_validation` | Finalize the test to confirm that instantiating a `Concept` with `resonance < -1.0` raises a `pydantic.ValidationError`. |
| **2.13**| `test_error_handling_for_message_with_missing_key` | Publish a message to `documents.pending` that lacks the `text` key. Verify that the service logs a warning, does not crash, and does not publish an output message. |
| **2.14**| `test_error_handling_for_malformed_json_message` | Publish a non-JSON string to `documents.pending`. Verify that the consumer logs the parsing error gracefully and continues running without interruption. |

---

### **4.0 Action Items**

1.  **Development & QA Teams:** Begin work immediately on the tasks assigned in the breakdown above. Prioritize the implementation tasks in **Story-611** before moving to the integration tests in **Story-612**.
2.  **All Team Members:** Refer to the **SYNLGLYPH Project Hub** as the single source of truth for all technical specifications, test plans, and code artifacts related to this sprint. All work should align with the documents contained therein.