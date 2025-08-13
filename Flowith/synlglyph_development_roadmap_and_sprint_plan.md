# **SYNLGLYPH: Development Roadmap & Sprint Plan**

**Objective:** This document outlines the strategic development plan for the SYNLGLYPH project. It translates the system architecture and code structure into a series of actionable epics, tasks, and milestones, providing a clear path from concept to a functional, testable system.

---

### **1. Project Epics: Strategic Development Pillars**

The project is organized into three core epics. These pillars represent the major, separable components of work required to deliver the SYNL_GLYPH platform.

| Epic ID | Epic Name | Description | Key Components |
| :--- | :--- | :--- | :--- |
| **EPIC-001** | Core Service Foundation | Focuses on building the `nous_service`, including its API, data models, and the initial structure for the semantic processing logic. This epic delivers the central "brain" of the system. | `nous_service`, FastAPI, Pydantic Schemas |
| **EPIC-002** | Event-Driven Pipeline | Encompasses the creation of the `glyph_bus` library and its integration into the `nous_service` to establish the asynchronous, Kafka-based communication backbone. | `glyph_bus`, Kafka Integration, Producer/Consumer Logic |
| **EPIC-003** | Robustness & Deployment | Covers all aspects of testing and deployment, including the `Selene` integration test suite, containerization with Docker, and establishing a reliable local development environment. | `Selene` (pytest), `Testcontainers`, Docker |

---

### **2. Task Breakdown by Epic**

Here are the key user stories and technical tasks required to fulfill each epic.

#### **EPIC-001: Core Service Foundation**

*   **Task-101:** Initialize `nous_service` FastAPI project structure according to the architecture blueprint.
*   **Task-102:** Define core Pydantic data models in `app/api/v1/schemas.py` (`Concept`, `AnalysisRequest`, `AnalysisResponse`).
*   **Task-103:** Implement the `/analyze` endpoint in `app/api/v1/endpoints/analysis.py` to accept POST requests and return a `202 Accepted` response.
*   **Task-104:** Create the placeholder `SemanticProcessor` class in `app/services/semantic_processor.py` with a stubbed `process_document` method.
*   **Task-105:** Implement basic application configuration management in `app/core/config.py` for settings like environment variables.
*   **Task-106:** Develop the `EventPublisher` service in `app/services/event_publisher.py` to act as an abstraction layer for the producer.

#### **EPIC-002: Event-Driven Pipeline**

*   **Task-201:** Set up the `glyph_bus` standalone library project with a `setup.py`.
*   **Task-202:** Implement the `GlyphProducer` class in `glyph_bus/producer.py` with `start`, `stop`, and `send_message` methods.
*   **Task-203:** Implement the `GlyphConsumer` class in `glyph_bus/consumer.py` to support asynchronous iteration over a topic.
*   **Task-204:** Integrate `GlyphProducer` into the `nous_service`'s `EventPublisher` and trigger message publication from the `/analyze` endpoint.
*   **Task-205:** Develop a background worker process/script within `nous_service` that uses `GlyphConsumer` to listen to the `documents.pending` topic.
*   **Task-206:** Wire the background worker to invoke the `SemanticProcessor.process_document` method for each consumed message.

#### **EPIC-003: Robustness & Deployment**

*   **Task-301:** Create a `Dockerfile` for the `nous_service` to build a production-ready container image.
*   **Task-302:** Develop a `docker-compose.yml` file to orchestrate the `nous_service` and a Kafka container for a complete local development environment.
*   **Task-303:** Initialize the `tests/` directory with `pytest` and configure `Testcontainers` in `integration/conftest.py` to provide an ephemeral Kafka instance for tests.
*   **Task-304:** Write unit tests for the `glyph_bus` library to validate producer and consumer functionality in isolation.
*   **Task-305:** Implement the end-to-end integration test `test_e2e_pipeline.py` which uses `GlyphProducer` to send a message and `GlyphConsumer` to assert the final result is received.
*   **Task-306:** Develop initial behavioral tests (`test_invariance.py`) to check that simple semantic equivalents are processed similarly.

---

### **3. Sample Sprint Plan: Sprint 1 (2 Weeks)**

**Sprint Goal:** *Establish the foundational skeleton of the system. By the end of this sprint, a developer should be able to send a request to a containerized API endpoint, see a message published to Kafka, and have the basic project structures for all major components in place.*

| Task ID | Epic | Story / Task | Priority | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Task-101** | EPIC-001 | Initialize `nous_service` FastAPI project structure. | **High** | To Do |
| **Task-102** | EPIC-001 | Define core Pydantic schemas (`AnalysisRequest`, `AnalysisResponse`). | **High** | To Do |
| **Task-301** | EPIC-003 | Create `Dockerfile` for `nous_service`. | **High** | To Do |
| **Task-302** | EPIC-003 | Develop `docker-compose.yml` for `nous_service` & Kafka. | **High** | To Do |
| **Task-201** | EPIC-002 | Set up `glyph_bus` library project structure. | **Medium** | To Do |
| **Task-202** | EPIC-002 | Implement the `GlyphProducer` class in `glyph_bus`. | **Medium** | To Do |
| **Task-103** | EPIC-001 | Implement the `/analyze` endpoint (stubbed, no Kafka call yet). | **Medium** | To Do |
| **Task-204** | EPIC-002 | Integrate `GlyphProducer` to publish a message from the `/analyze` endpoint. | **Medium** | To Do |
| **Task-303** | EPIC-003 | *[Stretch Goal]* Configure `pytest` with `Testcontainers` in `conftest.py`. | **Low** | To Do |

**Sprint Rationale:** This sprint prioritizes a "vertical slice" of the architecture. We focus on establishing the entry point (`nous_service` API), the communication channel (`glyph_bus` producer), and the environment (`Docker`). This approach validates the core architectural assumptions early and provides a tangible, runnable artifact for future development.

---

### **4. Project Milestones**

These milestones represent key delivery points that demonstrate significant progress and value.

1.  **M1: Local Pipeline Functional (End of Sprint 2)**
    *   **Definition of Done:** The complete data flow can be executed on a local machine via `docker-compose`. A request to the `/analyze` endpoint results in a message being produced to `documents.pending` and a separate consumer process logs the reception of that message.
    *   **Verifies:** Core inter-service communication via Kafka is working.

2.  **M2: `glyph_bus` Library v1.0.0 Release (End of Sprint 3)**
    *   **Definition of Done:** The `glyph_bus` library is fully tested, documented, and published to a private package repository. It is considered a stable internal dependency.
    *   **Verifies:** The communication abstraction is robust and reusable.

3.  **M3: `nous_service` Alpha Version (End of Sprint 5)**
    *   **Definition of Done:** The `SemanticProcessor` contains the first version of the actual NLP logic (e.g., entity extraction using `spaCy`). It consumes from `documents.pending` and publishes a structured `Concept` object to `concepts.completed`.
    *   **Verifies:** The core value proposition—transforming text to a concept model—is functional.

4.  **M4: End-to-End Integration Test Suite Passing (End of Sprint 6)**
    *   **Definition of Done:** The `Selene` test suite (`test_e2e_pipeline.py`) automatically spins up all required services, sends a test request, and validates the final `Concept` message on the output topic, all within a CI/CD pipeline.
    *   **Verifies:** The system is correct, reliable, and ready for automated quality gates.