import uvicorn
from SynergesisCore_DeepSeek_Pro_Complete import SynergesisAPI


class _DummyClusterer:
    def __init__(self):
        # start with a single empty log entry to avoid index errors
        self.performance_log = [[]]


class _DummyMemory:
    def __init__(self):
        self.patterns = []
        self.clusterer = _DummyClusterer()


class _DummyCore:
    """Minimal stub core compatible with SynergesisAPI.

    The real Synergesis engine is not provided in this light package. We only
    implement the attributes/methods referenced inside SynergesisAPI so that
    the FastAPI server can start and accept requests for demo purposes.
    """

    def __init__(self):
        self.memory = _DummyMemory()

    # The API expects a method ``process_input`` that appends to memory.patterns
    def process_input(self, state, context=""):
        # In a real engine this would do advanced processing; here we store a
        # simple UUID to mimic pattern creation.
        self.memory.patterns.append(len(self.memory.patterns) + 1)


# Instantiate FastAPI via SynergesisAPI
core = _DummyCore()
api = SynergesisAPI(core)
app = api.app  # This is what uvicorn will run


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
