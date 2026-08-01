import sys
sys.stdout.reconfigure(encoding='utf-8')

import uvicorn
from api.main import app

if __name__ == "__main__":
    print("Starting AI Video Studio Pro server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
