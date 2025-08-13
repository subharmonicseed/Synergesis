# main.py - Synergesis API Entry Point

from fastapi import FastAPI, HTTPException
from typing import Dict, Any, List
import numpy as np

# Import the integrated, advanced core
from synergesis.core import SynergesisCore

def convert_numpy_to_native(data: Any) -> Any:
    """
    Recursively converts numpy arrays, numeric types, and complex numbers to native
    Python types in a dictionary or list, making them JSON-serializable.
    """
    if isinstance(data, dict):
        return {k: convert_numpy_to_native(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_numpy_to_native(i) for i in data]
    if isinstance(data, np.ndarray):
        # .tolist() converts numpy types to native python types
        return convert_numpy_to_native(data.tolist())
    if isinstance(data, np.datetime64):
        return str(data)  # Convert datetime64 to ISO string
    if isinstance(data, (np.int64, np.int32, np.float64, np.float32)):
        return data.item()
    if isinstance(data, (complex, np.complex128, np.complex64)):
        return {'real': data.real, 'imag': data.imag}
    return data

class SynergesisAPI:
    def __init__(self, core: SynergesisCore):
        self.app = FastAPI(
            title="Synergesis Engine API",
            description="API for the Synergesis Semantic Engine.",
            version="1.2.0",
        )
        self.core = core
        self.add_endpoints()

    def add_endpoints(self):
        @self.app.post("/process", tags=["Core"])
        async def process_data(data: Dict[str, Any]):
            """
            Process an incoming data payload with the advanced core.

            - **state**: A list of numbers (real or complex) representing a vector.
            - **context**: A string providing context for the state.
            """
            try:
                state_list = data.get('state')
                if state_list is None:
                    raise HTTPException(status_code=400, detail="Missing 'state' in request body.")

                context = data.get('context', "No context provided.")
                state_np = np.array(state_list, dtype=complex)

                # Process with the advanced core, which now returns a Glyph object
                result_glyph = self.core.process_input(state_np, context)

                # Convert the Glyph model to a dict and clean for JSON output
                glyph_dict = result_glyph.model_dump()
                json_compatible_result = convert_numpy_to_native(glyph_dict)

                return {"status": "success", "result": json_compatible_result}

            except HTTPException as he:
                # Re-raise HTTPException to let FastAPI handle it
                raise he
            except Exception as e:
                print(f"Error processing request: {e}")
                raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")

        @self.app.get("/cluster_info", tags=["Analysis"])
        def get_clusters():
            """
            Get the latest clustering performance information.
            """
            if not self.core.clusterer.performance_log:
                return {
                    "cluster_info": "No clustering performed yet.",
                    "total_patterns_processed": len(self.core.memory)
                }

            latest_log = self.core.clusterer.performance_log[-1]
            return {
                "latest_cluster_log": convert_numpy_to_native(latest_log),
                "total_patterns_processed": len(self.core.memory)
            }

        @self.app.get("/status", tags=["System"])
        def get_status():
            """Returns the operational status of the API and its core."""
            return {
                "status": "ok",
                "core": self.core.__class__.__name__,
                "clusterer": self.core.clusterer.__class__.__name__,
                "validator": self.core.validator.__class__.__name__,
            }


def create_app() -> FastAPI:
    """Factory to create the FastAPI application."""
    core = SynergesisCore()
    api = SynergesisAPI(core)
    return api.app

# Create the app instance for the Uvicorn server
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
