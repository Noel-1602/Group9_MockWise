import os
import sys
from pathlib import Path
import uvicorn

# Ensure app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    default_port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="127.0.0.1", port=default_port, reload=True)

