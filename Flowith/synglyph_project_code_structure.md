### **SYNLGLYPH: Project Code Structure**

This document outlines the proposed code and directory structure for the SYNLGLYPH project. It is designed to promote modularity, clear separation of concerns, and robust testing, directly reflecting the principles laid out in the System Architecture Document.

---

### **1. Semantic Modeling Service (`nous_service`)**

This service is the core application responsible for semantic analysis. The structure is based on common practices for building scalable web services in Python with FastAPI, separating API endpoints, business logic, and data models.

```
nous_service/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   └── analysis.py
│   │   │   └── schemas.py
│   │   └── deps.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── event_publisher.py
│   │   └── semantic_processor.py
│   └── main.py
├── Dockerfile
└── requirements.txt
```

---

#### **Key File Content**

**app/api/v1/schemas.py**
*This file defines the data contracts for the system. Using Pydantic ensures data validation and provides clear, self-documenting models.*

```python
# app/api/v1/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid

class Relationship(BaseModel):
    """Defines a directed connection between two Concepts."""
    target_concept_id: uuid.UUID = Field(..., description="The ID of the concept this relationship points to.")
    type: str = Field(..., example="is_a", description="The nature of the relationship (e.g., 'is_a', 'part_of', 'causes').")
    weight: float = Field(default=1.0, description="The strength or confidence of the relationship.")

class Concept(BaseModel):
    """The core data model representing a semantic entity."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique identifier for the concept.")
    name: str = Field(..., example="Artificial Intelligence", description="The primary name or label for the concept.")
    aliases: List[str] = Field(default_for_factory=list, example=["AI", "Machine Intelligence"], description="Alternative names or synonyms.")
    description: Optional[str] = Field(None, description="A brief, generated summary of the concept.")
    weight: float = Field(..., ge=0.0, le=1.0, description="Conceptual importance within the source context (0.0 to 1.0).")
    resonance: float = Field(..., ge=-1.0, le=1.0, description="Contextual sentiment or emotional charge (-1.0 to 1.0).")
    relationships: List[Relationship] = Field(default_for_factory=list, description="List of relationships to other concepts.")
    metadata: Dict[str, any] = Field(default_for_factory=dict, description="Additional metadata, e.g., source document ID.")

class AnalysisRequest(BaseModel):
    """API model for an incoming analysis request."""
    text: str = Field(..., min_length=10, description="The raw text content to be analyzed.")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="A unique identifier for tracking the request.")

class AnalysisResponse(BaseModel):
    """API model for the response acknowledging an analysis job."""
    message: str = "Analysis job accepted."
    job_id: str
    status_topic: str
```

**app/api/v1/endpoints/analysis.py**
*This file contains the API route handler. It delegates the complex work to the service layer and immediately returns an acknowledgement to the client, fitting an asynchronous processing model.*

```python
# app/api/v1/endpoints/analysis.py
from fastapi import APIRouter, Depends, status, BackgroundTasks
from app.api.v1 import schemas
from app.services.event_publisher import EventPublisher
from app.api.deps import get_event_publisher

router = APIRouter()

@router.post(
    "/analyze",
    response_model=schemas.AnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit text for semantic analysis"
)
async def analyze_text(
    request: schemas.AnalysisRequest,
    background_tasks: BackgroundTasks,
    publisher: EventPublisher = Depends(get_event_publisher)
):
    """
    Accepts raw text and queues it for asynchronous processing.

    - Publishes the text to the `documents.pending` Kafka topic.
    - Immediately returns a job ID for tracking.
    """
    # The actual publishing is done in the background to avoid blocking the API response.
    background_tasks.add_task(
        publisher.publish_pending_document,
        request_id=request.request_id,
        text=request.text
    )

    return schemas.AnalysisResponse(
        job_id=request.request_id,
        status_topic=f"analysis.status.{request.request_id}"
    )
```

**app/services/semantic_processor.py**
*This represents the service that consumes from Kafka, performs the heavy lifting, and would contain the core NLP/ML logic.*

```python
# app/services/semantic_processor.py
from app.api.v1.schemas import Concept
from app.services.event_publisher import EventPublisher
# Placeholder for actual NLP libraries
# import spacy
# from transformers import pipeline

class SemanticProcessor:
    """
    Consumes messages from the 'documents.pending' topic,
    runs the semantic modeling pipeline, and publishes the
    resulting Concept model to the 'concepts.completed' topic.
    """
    def __init__(self, publisher: EventPublisher):
        # self.nlp = spacy.load("en_core_web_trf")
        # self.rag_pipeline = pipeline(...)
        self.publisher = publisher
        print("Semantic Processor initialized.")

    async def process_document(self, message: dict):
        """
        The core processing logic for a single document.
        """
        text = message.get("text")
        request_id = message.get("request_id")

        print(f"Processing document for request_id: {request_id}")

        # 1. Perform NLP (entity recognition, parsing, etc.)
        # doc = self.nlp(text)

        # 2. Use RAG or other models to enrich data

        # 3. Construct the Concept object(s)
        # This is a stubbed example
        main_concept = Concept(
            name="Example Concept",
            weight=0.87,
            resonance=0.3,
            metadata={"request_id": request_id}
        )

        # 4. Publish the completed concept
        await self.publisher.publish_completed_concept(concept=main_concept)
        print(f"Finished processing and published concept for request_id: {request_id}")
```

---

### **2. Glyph_Bus Client Library**

This is a standalone, installable Python package designed to abstract away the complexities of interacting with Kafka. It provides simple, high-level Producer and Consumer classes for other services to use.

```
glyph_bus/
├── glyph_bus/
│   ├── __init__.py
│   ├── config.py
│   ├── consumer.py
│   ├── exceptions.py
│   └── producer.py
├── setup.py
└── README.md
```

#### **Key File Content**

**glyph_bus/producer.py**
*Provides a simple interface for sending messages to Kafka topics.*

```python
# glyph_bus/producer.py
import json
from aiokafka import AIOKafkaProducer
from .config import KafkaConfig

class GlyphProducer:
    """A simple wrapper around AIOKafkaProducer for sending messages."""

    def __init__(self, config: KafkaConfig):
        self._producer = AIOKafkaProducer(
            bootstrap_servers=config.bootstrap_servers
        )
        self._is_started = False

    async def start(self):
        """Connects the producer to the Kafka cluster."""
        await self._producer.start()
        self._is_started = True

    async def stop(self):
        """Gracefully disconnects the producer."""
        await self._producer.stop()
        self._is_started = False

    async def send_message(self, topic: str, message: dict, key: str = None):
        """
        Serializes a dictionary to JSON and sends it to a Kafka topic.

        Args:
            topic: The Kafka topic to publish to.
            message: A dictionary payload.
            key: An optional message key (string).
        """
        if not self._is_started:
            raise RuntimeError("Producer has not been started. Call start() first.")
        
        value = json.dumps(message).encode('utf-8')
        key_bytes = key.encode('utf-8') if key else None
        
        await self._producer.send_and_wait(topic, value=value, key=key_bytes)
```

**glyph_bus/consumer.py**
*Provides a high-level async iterator to consume and process messages from a topic.*

```python
# glyph_bus/consumer.py
import json
from aiokafka import AIOKafkaConsumer
from .config import KafkaConfig

class GlyphConsumer:
    """A simple wrapper around AIOKafkaConsumer for receiving messages."""

    def __init__(self, config: KafkaConfig, topics: list[str], group_id: str):
        self._consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=config.bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest' # Start from the beginning of a topic
        )
        self._is_started = False

    async def start(self):
        await self._consumer.start()
        self._is_started = True

    async def stop(self):
        await self._consumer.stop()
        self._is_started = False

    async def __aiter__(self):
        if not self._is_started:
            raise RuntimeError("Consumer has not been started. Call start() first.")
        return self

    async def __anext__(self):
        """Allows for iterating over messages with `async for`."""
        message = await self._consumer.getone()
        try:
            # Decode and deserialize the message value
            return json.loads(message.value.decode('utf-8'))
        except (json.JSONDecodeError, AttributeError):
            # Handle potential malformed messages gracefully
            return None
```

---

### **3. Selene Integration Testing Suite**

This structure organizes tests using `pytest`. The most critical component is `conftest.py`, which uses `Testcontainers` to provide ephemeral, isolated instances of dependencies like Kafka for each test session, ensuring reliable and repeatable test runs.

```
tests/
├── integration/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_e2e_pipeline.py
│   └── test_nous_service_contracts.py
├── behavioral/
│   ├── __init__.py
│   ├── test_invariance.py
│   └── test_directional.py
├── utils/
│   ├── __init__.py
│   └── kafka_helpers.py
├── pytest.ini
└── requirements.txt
```

#### **Key File Content**

**integration/conftest.py**
*This fixture setup is the foundation of the integration test suite. It programmatically manages the lifecycle of a Kafka container.*

```python
# integration/conftest.py
import pytest
import pytest_asyncio
from testcontainers.kafka import KafkaContainer
from glyph_bus.config import KafkaConfig

@pytest.fixture(scope="session")
def kafka_container():
    """
    Spins up a Kafka container for the entire test session.
    The `with` statement ensures the container is stopped and removed
    after all tests in the session have completed.
    """
    with KafkaContainer(image="confluentinc/cp-kafka:7.0.1") as kafka:
        yield kafka

@pytest_asyncio.fixture(scope="session")
async def kafka_config(kafka_container: KafkaContainer) -> KafkaConfig:
    """Provides Kafka connection details as a Pydantic model."""
    bootstrap_servers = kafka_container.get_bootstrap_server()
    return KafkaConfig(bootstrap_servers=bootstrap_servers)
```

**integration/test_e2e_pipeline.py**
*An example of a full end-to-end test that simulates the entire data flow described in the architecture document.*

```python
# integration/test_e2e_pipeline.py
import pytest
import asyncio
from glyph_bus.producer import GlyphProducer
from glyph_bus.consumer import GlyphConsumer
from glyph_bus.config import KafkaConfig

# Mark as an asyncio test for pytest
pytestmark = pytest.mark.asyncio

async def test_full_analysis_pipeline(kafka_config: KafkaConfig):
    """
    Tests the complete pipeline:
    1. A 'client' (test producer) sends a document to 'documents.pending'.
    2. A 'processor' (simulated here) would read this message.
    3. The test waits for a result on the 'concepts.completed' topic.
    4. The test consumer validates the received concept.
    """
    # Test constants
    PENDING_TOPIC = "documents.pending"
    COMPLETED_TOPIC = "concepts.completed"
    GROUP_ID = "test-pipeline-group"
    
    # 1. Setup client producer and results consumer
    producer = GlyphProducer(config=kafka_config)
    consumer = GlyphConsumer(config=kafka_config, topics=[COMPLETED_TOPIC], group_id=GROUP_ID)
    
    await producer.start()
    await consumer.start()

    # **ARRANGE**: Define the input document and the expected output
    test_document = {"request_id": "e2e-123", "text": "The quick brown fox jumps over the lazy dog."}
    # In a real scenario, a simulated Nous service would run here and produce the message.
    # For this test, we'll manually produce the "completed" message.
    expected_concept = {"id": "some-uuid", "name": "Quick Brown Fox", "weight": 0.9}

    # **ACT**: Publish the test document and the simulated result
    await producer.send_message(topic=PENDING_TOPIC, message=test_document)
    # Simulate the processor's output
    await producer.send_message(topic=COMPLETED_TOPIC, message=expected_concept)

    # **ASSERT**: Consume the result and validate it
    try:
        # Wait for the result with a timeout
        received_concept = await asyncio.wait_for(consumer.__anext__(), timeout=5.0)
        
        assert received_concept is not None
        assert received_concept["name"] == expected_concept["name"]
        assert received_concept["weight"] == expected_concept["weight"]

    finally:
        # Teardown
        await producer.stop()
        await consumer.stop()
```