"""Server runner for the Codebase Audit Platform API."""

import os
import uvicorn
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("run:app", host="0.0.0.0", port=port, reload=True)
