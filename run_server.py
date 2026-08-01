"""
AI Video Studio Pro — Main Server
รัน FastAPI server
"""

import uvicorn
import sys
import os

# เพิ่ม path สำหรับ imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """รัน server"""
    print("=" * 50)
    print("  AI Video Studio Pro v2.0")
    print("  ระบบตัดต่อด้วย AI อัตโนมัติ")
    print("=" * 50)
    print()
    print("Starting server...")
    print("API: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    print("Frontend: http://localhost:8000")
    print()
    print("Press Ctrl+C to stop")
    print()
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
