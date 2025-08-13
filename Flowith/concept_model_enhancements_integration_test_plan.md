### **Integration Test Plan: Concept Model Enhancements (`weight` & `resonance`)**
**Document ID:** TP-20250717-CME-SELENE
**Version:** 1.0
**Status:** Draft
**Author:** QA Analyst, Selene Team
**Date:** July 17, 2025

---

### 1.0 Introduction

#### **1.1 Purpose**
This document outlines the integration test plan for validating the 'Concept' model enhancements within the `nous_service`. The primary focus is to verify the correctness of the new `weight` and `resonance` calculation logic and ensure its seamless integration into the existing event-driven architecture powered by `glyph_bus` (Apache Kafka).

#### **1.2 Scope**
This plan covers the end-to-end testing of features implemented as part of Sprint 2, specifically tasks `Task-401` through `Task-406`. The scope includes:
-   Validation of the business logic in `semantic_processor.py`.
-   Verification of the updated Pydantic `Concept` model in `schemas.py`.
-   End-to-end message flow validation from the `documents.pending` topic to the `concepts.completed` topic.

#### **1.3 Assumptions**
This test plan is based on the final code implementation as detailed in the `concept model enhancement code implementation.md` document. It is noted that the implemented calculation logic for `weight` (logistic function on word count) and `resonance` (keyword matching) differs from the initial approach outlined in the technical specification (`TS-20250717-CME-02`). This plan will validate the **as-built** functionality.

---

### 2.0 Test Items
The following components of the SYNLGLYPH system are subject to testing under this plan.

| Item Type | Identifier | File Path / Component Name | Description |
| :--- | :--- | :--- | :--- |
| **Service** | `nous_service` | `nous_service/` | The core microservice responsible for semantic processing. |
| **Module** | `Concept Model` | `app/api/v1/schemas.py` | The Pydantic data model. Testing focuses on the optional `weight` and `resonance` fields. |
| **Module** | `SemanticProcessor` | `app/services/semantic_processor.py` | The class containing the business logic for calculating `weight` and `resonance`. |
| **Function** | `_calculate_weight` | `semantic_processor.py` | The specific function that calculates conceptual weight based on text length. |
| **Function** | `_calculate_resonance` | `semantic_processor.py` | The specific function that calculates contextual resonance based on keyword matching. |
| **Integration Point** | `glyph_bus` | Apache Kafka Topics | The message bus used for communication. Tests will verify serialization/deserialization across `documents.pending` and `concepts.completed` topics. |

---

### 3.0 Features to be Tested
The following tables detail the specific test cases designed to validate the new features.

#### **3.1 Correctness of Calculations**

These tests verify that the calculation logic produces expected results for a given range of inputs.

| Test Case ID | Feature | Input Text Description | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-COR-01** | `weight` | Short text (20 words) | Weight is low (e.g., `< 0.2`). |
| **TC-COR-02** | `weight` | Medium text (50 words - the midpoint) | Weight is approximately `0.5`. |
| **TC-COR-03** | `weight` | Long text (150 words) | Weight approaches `1.0` (e.g., `> 0.9`). |
| **TC-COR-04** | `resonance` | Contains only positive keywords (e.g., "good", "excellent", "success") | Resonance is exactly `1.0`. |
| **TC-COR-05** | `resonance` | Contains only negative keywords (e.g., "bad", "problem", "failure") | Resonance is exactly `-1.0`. |
| **TC-COR-06** | `resonance` | Contains an equal number of positive and negative keywords | Resonance is exactly `0.0`. |
| **TC-COR-07** | `resonance` | Contains no positive or negative keywords | Resonance is exactly `0.0` (neutral). |

#### **3.2 Integration & Data Flow**
This test verifies the end-to-end pipeline.

| Test Case ID | Feature | Test Scenario | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-INT-01** | E2E Pipeline | 1. Publish a valid `AnalysisRequest` JSON to `documents.pending`. <br> 2. `Selene` consumer listens to `concepts.completed`. | 1. `nous_service` consumes the message without error. <br> 2. A single `Concept` message is published to `concepts.completed`. <br> 3. The consumed message successfully deserializes into the Pydantic `Concept` model. <br> 4. The `weight` and `resonance` fields are present, are of type `float`, and have non-null values within their defined constraints. |

#### **3.3 Edge Cases**
These tests validate the system's behavior under boundary conditions.

| Test Case ID | Feature | Input | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-EDG-01** | `weight` / `resonance` | Empty string `""` as input text. | Service does not crash. `_calculate_weight` returns a valid float. `_calculate_resonance` returns `0.0`. |
| **TC-EDG-02** | `weight` / `resonance` | Text containing only whitespace and punctuation. | Service does not crash. `_calculate_weight` returns a valid float. `_calculate_resonance` returns `0.0`. |
| **TC-EDG-03** | Pydantic Model | A `Concept` object is instantiated with `weight` = `1.5`. | A `pydantic.ValidationError` should be raised due to the `le=1.0` constraint. This is a unit-level check for the schema itself. |
| **TC-EDG-04** | Pydantic Model | A `Concept` object is instantiated with `resonance` = `-2.0`. | A `pydantic.ValidationError` should be raised due to the `ge=-1.0` constraint. This is a unit-level check for the schema itself. |

#### **3.4 Error Handling**
This test validates the robustness of the consumer when receiving malformed data.

| Test Case ID | Feature | Input | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **TC-ERR-01** | `process_document` | A JSON message on `documents.pending` missing the required `text` key. | 1. The service logs a "Skipping malformed message" warning. <br> 2. The service does **not** crash. <br> 3. No message is published to `concepts.completed`. <br> 4. The service continues to process subsequent valid messages correctly. |
| **TC-ERR-02** | `process_document` | A JSON message on `documents.pending` that is not valid JSON. | The `AIOKafkaConsumer` or JSON parser handles the error gracefully. The service logs the error and continues running without crashing. |

---

### 4.0 Test Environment & Prerequisites

| Category | Requirement | Details |
| :--- | :--- | :--- |
| **Hardware** | Development Machine | Standard developer-grade laptop or desktop (e.g., 16GB RAM, multi-core CPU). |
| **Software** | Containerization | `Docker` and `docker-compose`. |
| **Software** | Test Framework | `pytest` |
| **Software** | Test Dependencies | `testcontainers` for managing ephemeral Kafka instances. `aiokafka` for interacting with topics. |
| **Environment** | Test Runner | The `Selene` test suite. |
| **Data** | Test Data | A collection of predefined text files and JSON payloads corresponding to the test cases outlined in Section 3.0. |
| **Prerequisites**| Code & Config | The `nous_service` and `glyph_bus` repositories must be cloned and available. The `docker-compose.yml` file must be correctly configured to launch the `nous_service` and its dependencies. |

---

### 5.0 Success Criteria

The 'Concept' model enhancement feature will be considered successfully validated and ready for promotion to the next environment when all of the following criteria are met:

1.  **Full Test Execution:** 100% of the test cases defined in this plan (TC-COR, TC-INT, TC-EDG, TC-ERR) have been executed.
2.  **Passing Rate:** 100% of the executed test cases pass without any failures.
3.  **Calculation Accuracy:** For all `Correctness` test cases (TC-COR), the calculated `weight` and `resonance` values must match the expected values within a tolerance of `±0.0001`.
4.  **Pipeline Integrity:** The end-to-end integration test (TC-INT-01) must pass, confirming that messages flow through the system and that the final `Concept` object is structurally valid and contains plausible data.
5.  **Robustness:** All `Edge Case` and `Error Handling` tests must pass, demonstrating that the service handles unexpected or invalid data gracefully without crashing or corrupting its state.
6.  **No Regressions:** All pre-existing tests in the `Selene` suite must continue to pass, ensuring that the new features have not introduced any regressions.