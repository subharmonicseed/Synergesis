from synergesis.core.deepseek_pro import SynergesisCoreDeepSeekPro, SynergesisAPI
import uvicorn
import os

# Instantiate the core system and API wrapper
core = SynergesisCoreDeepSeekPro()
api = SynergesisAPI(core)

if __name__ == "__main__":
    # Allow port override via environment variable for flexibility
    port = int(os.getenv("SYNERGESIS_PORT", "8000"))
    uvicorn.run(api.app, host="0.0.0.0", port=port, reload=False)
