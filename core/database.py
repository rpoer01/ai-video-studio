"""
Database — SQLite Database สำหรับเก็บข้อมูล
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import os


DB_PATH = "ai_video_studio.db"


class Database:
    """
    SQLite Database สำหรับ AI Video Studio
    
    ใช้เก็บ:
    - Projects: โปรเจค
    - Files: ไฟล์มีเดีย
    - Jobs: งานที่กำลังทำ
    - Assets: คลังมีเดีย
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """สร้างตาราง"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # ตาราง Projects
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # ตาราง Files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT,
                    file_size INTEGER,
                    duration REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # ตาราง Jobs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    job_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    input_data TEXT,
                    output_data TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            """)
            
            # ตาราง Assets (คลังมีเดีย)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    asset_type TEXT,
                    file_path TEXT,
                    tags TEXT,
                    mood TEXT,
                    category TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # ตาราง Highlights
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS highlights (
                    id TEXT PRIMARY KEY,
                    file_id TEXT,
                    start_time REAL,
                    end_time REAL,
                    score REAL,
                    reason TEXT,
                    keywords TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """)
            
            conn.commit()

    # Project CRUD
    def create_project(self, name: str, description: str = "", metadata: Dict = None) -> str:
        """สร้างโปรเจคใหม่"""
        project_id = f"proj_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO projects (id, name, description, metadata) VALUES (?, ?, ?, ?)",
                (project_id, name, description, json.dumps(metadata or {}))
            )
            conn.commit()
        
        return project_id

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลโปรเจค"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "metadata": json.loads(row[5]) if row[5] else {}
                }
        return None

    def list_projects(self) -> List[Dict[str, Any]]:
        """รายชื่อโปรเจคทั้งหมด"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": row[3]
                }
                for row in rows
            ]

    def update_project(self, project_id: str, **kwargs) -> bool:
        """อัปเดตโปรเจค"""
        allowed_fields = ["name", "description", "metadata"]
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        if "metadata" in updates:
            updates["metadata"] = json.dumps(updates["metadata"])
        
        updates["updated_at"] = datetime.now().isoformat()
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [project_id]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_project(self, project_id: str) -> bool:
        """ลบโปรเจค"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cursor.rowcount > 0

    # File CRUD
    def add_file(self, project_id: str, filename: str, file_path: str, 
                 file_type: str = None, file_size: int = None, 
                 duration: float = None, metadata: Dict = None) -> str:
        """เพิ่มไฟล์"""
        file_id = f"file_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO files (id, project_id, filename, file_path, 
                   file_type, file_size, duration, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, project_id, filename, file_path, 
                 file_type, file_size, duration, json.dumps(metadata or {}))
            )
            conn.commit()
        
        return file_id

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลไฟล์"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "project_id": row[1],
                    "filename": row[2],
                    "file_path": row[3],
                    "file_type": row[4],
                    "file_size": row[5],
                    "duration": row[6],
                    "created_at": row[7],
                    "metadata": json.loads(row[8]) if row[8] else {}
                }
        return None

    def list_files(self, project_id: str) -> List[Dict[str, Any]]:
        """รายชื่อไฟล์ในโปรเจค"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE project_id = ?", (project_id,))
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "filename": row[2],
                    "file_type": row[4],
                    "duration": row[6]
                }
                for row in rows
            ]

    # Job CRUD
    def create_job(self, project_id: str, job_type: str, input_data: Dict = None) -> str:
        """สร้างงานใหม่"""
        job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO jobs (id, project_id, job_type, input_data) VALUES (?, ?, ?, ?)",
                (job_id, project_id, job_type, json.dumps(input_data or {}))
            )
            conn.commit()
        
        return job_id

    def update_job(self, job_id: str, status: str = None, 
                   output_data: Dict = None, error: str = None) -> bool:
        """อัปเดตสถานะงาน"""
        updates = {}
        if status:
            updates["status"] = status
            if status == "running":
                updates["started_at"] = datetime.now().isoformat()
            elif status in ["completed", "failed"]:
                updates["completed_at"] = datetime.now().isoformat()
        if output_data:
            updates["output_data"] = json.dumps(output_data)
        if error:
            updates["error"] = error
        
        if not updates:
            return False
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [job_id]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลงาน"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "project_id": row[1],
                    "job_type": row[2],
                    "status": row[3],
                    "input_data": json.loads(row[4]) if row[4] else {},
                    "output_data": json.loads(row[5]) if row[5] else {},
                    "error": row[6],
                    "created_at": row[7],
                    "started_at": row[8],
                    "completed_at": row[9]
                }
        return None

    # Asset CRUD
    def add_asset(self, name: str, asset_type: str, file_path: str,
                  tags: List[str] = None, mood: str = None, 
                  category: str = None, metadata: Dict = None) -> str:
        """เพิ่ม asset ในคลัง"""
        asset_id = f"asset_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO assets (id, name, asset_type, file_path, 
                   tags, mood, category, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (asset_id, name, asset_type, file_path,
                 json.dumps(tags or []), mood, category, json.dumps(metadata or {}))
            )
            conn.commit()
        
        return asset_id

    def search_assets(self, mood: str = None, category: str = None, 
                      tags: List[str] = None) -> List[Dict[str, Any]]:
        """ค้นหา assets"""
        query = "SELECT * FROM assets WHERE 1=1"
        params = []
        
        if mood:
            query += " AND mood = ?"
            params.append(mood)
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "asset_type": row[2],
                    "file_path": row[3],
                    "tags": json.loads(row[4]) if row[4] else [],
                    "mood": row[5],
                    "category": row[6]
                }
                for row in rows
            ]

    def close(self):
        """ปิดการเชื่อมต่อ"""
        pass  # SQLite จัดการเอง


# Global database instance
db = Database()


# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    print("=== Database Demo ===\n")
    
    # สร้างโปรเจค
    project_id = db.create_project("Test Project", "ทดสอบระบบ")
    print(f"Created project: {project_id}")
    
    # ดึงโปรเจค
    project = db.get_project(project_id)
    print(f"Project: {project}")
    
    # สร้างงาน
    job_id = db.create_job(project_id, "analyze", {"video_path": "test.mp4"})
    print(f"Created job: {job_id}")
    
    # อัปเดตงาน
    db.update_job(job_id, status="completed", output_data={"result": "success"})
    
    # ดึงงาน
    job = db.get_job(job_id)
    print(f"Job: {job}")
    
    # เพิ่ม asset
    asset_id = db.add_asset("Test Video", "video", "test.mp4", 
                           tags=["test", "demo"], mood="happy", category="general")
    print(f"Created asset: {asset_id}")
    
    # ค้นหา assets
    assets = db.search_assets(mood="happy")
    print(f"Assets with mood 'happy': {len(assets)}")
    
    # ลบโปรเจค
    db.delete_project(project_id)
    print(f"Deleted project: {project_id}")
    
    print("\n=== Demo Complete ===")
