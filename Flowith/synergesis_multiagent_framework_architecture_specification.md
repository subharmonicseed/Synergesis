# **Synergesis Framework: The Definitive Architectural Specification**

This document provides the authoritative overview of the Synergesis multi-agent framework. It synthesizes all strategic decisions and supersedes previous planning documents, including the initial Sprint 4 plan. Its purpose is to serve as the single source of truth for all subsequent design and development efforts.

---

### **1. Core Architectural Model: The Blackboard and the Control Loop**

The Synergesis framework is architected around two proven patterns for complex, intelligent systems: the **Blackboard** pattern for shared knowledge and the **MAPE-K** loop for autonomous control. This combination creates a resilient, scalable, and decentralized ecosystem for emergent problem-solving.

#### **The Blackboard Pattern: A Shared Universe of Knowledge**

At the heart of the framework lies the **World State DB**, a high-performance, centralized data store that functions as a classic blackboard.

*   **What is it?** A common space where all agents read their input and write their output. It holds the "world state"—the collective knowledge, raw data, intermediate findings, and final conclusions of the entire system.
*   **Why this pattern?** It decouples agents from one another. Agents do not need to know about each other's existence or location; they only need to know how to interact with the shared blackboard. This allows for:
    *   **Asynchronous Collaboration:** Agents can work at their own pace, contributing knowledge as it is generated.
    *   **Scalability:** New agents can be added to the system without reconfiguring existing ones.
    *   **Emergent Solutions:** Complex solutions can arise from the simple, independent contributions of many specialized agents.

#### **The MAPE-K Loop: An Engine for Orchestration**

The **Synergy Core** orchestrator, in conjunction with the agents, executes a continuous control loop known as MAPE-K (Monitor, Analyze, Plan, Execute over a shared Knowledge base).

> **MAPE-K Cycle in Synergesis:**
> 1.  **Monitor:** The `Synergy Core` and specialized agents like `AURA` constantly monitor the `World State DB` (the **K**nowledge base) for new tasks, state changes, or completion criteria defined in a `Metascript`.
> 2.  **Analyze:** The `Synergy Core` analyzes the current state against the goals of the `Metascript`, determining what kind of work needs to be done next.
> 3.  **Plan:** It formulates a plan by breaking down the goal into concrete tasks and identifying the appropriate agent capabilities required (e.g., "semantic analysis," "geometric reasoning").
> 4.  **Execute:** The `Synergy Core` dispatches these tasks to available, specialized agents. The agents execute their function, updating the `World State DB` and thus starting the cycle anew.



---

### **2. The Synergesis Agent Constellation**

The framework is designed to host a constellation of eight core, specialized agents. Each agent possesses a high degree of functional density and is designed for a specific purpose within the ecosystem. The `Glyph-Analyzer` concept from previous plans is now formalized as the **NOUS** agent.

| Agent | Primary Role | Key Interactions & Data Flow |
| :--- | :--- | :--- |
| **EOS** | **Ingestion & Initiation Agent.** The "dawn" of a process. EOS is responsible for ingesting external data, parsing initial `Metascripts`, and placing raw materials and initial tasks onto the World State DB. | - **Reads:** External data sources, user-submitted `Metascripts`. <br> - **Writes:** Raw data objects and initial `TaskPayloads` to the World State DB. <br> - **Triggers:** The first cycle of the `Synergy Core`. |
| **NOUS** | **Semantic Analysis Agent.** The core "mind" for understanding meaning. Built upon the `syn-engine` library, it analyzes symbolic and textual data to extract concepts, weight, and resonance. | - **Reads:** Data objects tagged for semantic analysis from the World State DB. <br> - **Writes:** Enriched data objects with semantic metadata (`Concept` models, `weight`, `resonance`) back to the World State DB. |
| **THALES** | **Logical & Geometric Reasoning Agent.** Named for the ancient philosopher, THALES handles formal logic, pattern recognition, and geometric/mathematical relationship analysis within the symbolic data. | - **Reads:** Semantically enriched data from NOUS. <br> - **Writes:** Inferred relationships, logical conclusions, and geometric patterns to the World State DB. |
| **AURA** | **System State & Context Agent.** AURA monitors the overall "health" and context of the World State DB. It observes emergent patterns, tracks system load, and provides contextual awareness for other agents. | - **Reads:** A broad view of the World State DB and system metrics. <br> - **Writes:** System context summaries, state-change alerts, and heuristic insights to the World State DB. |
| **SELENE** | **Quality & Validation Agent.** Evolving from its origins as a test suite, SELENE is responsible for quality assurance. It runs validation routines, checks for logical consistency, and verifies that agent outputs meet predefined standards. | - **Reads:** Agent outputs (`TaskResult`) and data objects. <br> - **Writes:** Validation reports, quality scores, and error flags to the World State DB. |
| **VYRA** | **Visualization & Rendering Agent.** (*V*isual *Y*ield & *R*endering *A*gent). VYRA translates abstract data and symbolic relationships from the World State DB into concrete, human-understandable visualizations (e.g., graphs, charts, renderings). | - **Reads:** Synthesized results and relationship data. <br> - **Writes:** Rendered artifacts (images, JSON for D3.js) to an output data store or the World State DB. |
| **LUMEN** | **Synthesis & Insight Agent.** The "light" of understanding. LUMEN's role is to synthesize the fragmented results from other agents into a coherent final report or answer, fulfilling the ultimate goal of the `Metascript`. | - **Reads:** Verified data, logical conclusions, and contextual summaries. <br> - **Writes:** The final, synthesized output to the World State DB. |
| **SYN-ECHO** | **Logging & Traceability Agent.** SYN-ECHO records the history of all operations. It ensures symbolic traceability by creating an immutable audit trail of which agent performed what action on which data, enabling perfect replay and debugging. | - **Reads:** All `TaskPayloads` and `TaskResults` across the system. <br> - **Writes:** A structured, time-series log to a dedicated, immutable log store. |

---

### **3. Communication Protocols & Interaction Cycles**

Communication within Synergesis is standardized and asynchronous, governed by a declarative scripting language and formal data contracts.

#### **The Interaction Cycle**

1.  **Declaration:** An operator or automated process defines a high-level goal in a `Metascript` file (e.g., `analyze_symbols.ms`).
2.  **Initiation:** The **EOS** agent ingests the `Metascript` and seeds the `World State DB` with the initial data and task.
3.  **Orchestration:** The **Synergy Core** detects the new task, parses the `Metascript`, and dispatches a `TaskPayload` to a suitable agent (e.g., **NOUS**).
4.  **Execution:** The agent receives the `TaskPayload`, reads its required data from the `World State DB`, performs its function, and writes a `TaskResult` back.
5.  **Iteration:** This result may trigger other agents. The cycle continues as agents collaboratively enrich the `World State DB` until the `Metascript`'s end-state conditions are met.
6.  **Synthesis:** The **LUMEN** agent detects the completion criteria and synthesizes the final output.

#### **Core Data Contracts**

All agent communication is mediated through two primary Pydantic models, ensuring type-safe and predictable data exchange.

| Model | Purpose | Fields |
| :--- | :--- | :--- |
| **`TaskPayload`** | A standardized structure for a work order dispatched by the Synergy Core to an agent. | `- task_id: str` <br> `- agent_type: str` <br> `- data: dict` (Flexible payload, e.g., keys to objects in World State DB) |
| **`TaskResult`** | A standardized structure for reporting the outcome of a task back to the framework. | `- task_id: str` <br> `- status: str` ('SUCCESS', 'FAILURE', 'ERROR') <br> `- result_data: dict` (Optional output data) |

---

### **4. Core Design Principles**

The Synergesis framework is built upon a set of core principles that guide its architecture and evolution.

| Principle | Description |
| :--- | :--- |
| **Functional Density** | Each agent should be highly specialized and potent. We favor a small number of powerful, expert agents over a large number of simple, single-function ones. |
| **Symbolic Traceability** | Every piece of data, insight, or conclusion in the system must be traceable back to its origins. The `SYN-ECHO` agent is the primary enabler of this principle. |
| **Decentralized Autonomy** | Agents operate as independent, containerized processes. They are managed by the `Synergy Core` but are autonomous in their execution, enhancing system resilience. |
| **Standardized Interoperability** | A strict `IAgent` interface and common data contracts are mandatory. This ensures any agent conforming to the standard can seamlessly join the ecosystem. |
| **Asynchronous Collaboration** | Agents do not communicate directly. All interaction is mediated through the `World State DB`, enabling robust, scalable, and non-blocking workflows. |
| **Declarative Orchestration** | System behavior is defined using the high-level `Metascript` language. We declare *what* we want to achieve, not *how* to achieve it, leaving the orchestration details to the `Synergy Core`. |

---

### **5. Minimal Implementation: The Synergesis Starter Kit**

To bootstrap the framework, development will begin with a "Starter Kit" that constitutes the first functional vertical slice of the ecosystem. This serves as the blueprint for Sprint 4 and beyond.

**Components of the Starter Kit:**
1.  **Framework Core:**
    *   **Synergy Core:** A basic implementation capable of parsing `Metascripts`, managing a task queue, and dispatching tasks.
    *   **World State DB:** A provisioned Redis or similar key-value store.
    *   **Metascript Engine:** A parser for a minimal viable version of the `.ms` language.

2.  **Agent Contract & Logic:**
    *   **`IAgent` Interface:** A defined abstract base class in Python with `initialize`, `execute_task`, and `shutdown` methods.
    *   **`syn-engine` Library:** The core semantic analysis algorithms from the legacy 'Syn' tool, refactored into a standalone, installable Python package.

3.  **The First Agent:**
    *   **`NOUS` Agent:** A containerized agent that implements the `IAgent` interface and uses the `syn-engine` library to perform its analysis. This agent serves as the reference implementation for all others.

4.  **End-to-End Test:**
    *   **Test Metascript:** A simple `test_analysis.ms` file that defines a task for the `NOUS` agent.
    *   **Test Orchestrator:** An automated test script that seeds the `World State DB`, submits the `Metascript`, and validates that the `NOUS` agent produces the correct `TaskResult`.