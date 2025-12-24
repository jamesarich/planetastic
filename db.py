"""
Planetastic: Database Management
Version: 2.1.0
Author: James Rich <james.a.rich@gmail.com>
"""
import aiosqlite
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS aircraft (
                    hex_ident TEXT PRIMARY KEY,
                    callsign TEXT,
                    altitude INTEGER,
                    ground_speed INTEGER,
                    track INTEGER,
                    lat REAL,
                    lon REAL,
                    vertical_rate INTEGER,
                    squawk INTEGER,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    data_json TEXT
                )
            ''')
            await db.commit()
            logger.info(f"Database initialized at {self.db_path}")

    async def update_aircraft(self, hex_ident: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            # Get existing data
            cursor = await db.execute("SELECT data_json, first_seen FROM aircraft WHERE hex_ident = ?", (hex_ident,))
            row = await cursor.fetchone()
            
            if row:
                existing_data = json.loads(row[0])
                first_seen = row[1]
            else:
                existing_data = {}
                first_seen = datetime.now().isoformat()

            # Merge new data
            for key, value in parsed_data.items():
                if value is not None and value != '':
                    existing_data[key] = value
            
            last_seen = datetime.now().isoformat()
            data_json = json.dumps(existing_data)
            
            await db.execute('''
                INSERT OR REPLACE INTO aircraft 
                (hex_ident, callsign, altitude, ground_speed, track, lat, lon, vertical_rate, squawk, first_seen, last_seen, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                hex_ident,
                existing_data.get('callsign'),
                existing_data.get('altitude'),
                existing_data.get('ground_speed'),
                existing_data.get('track'),
                existing_data.get('lat'),
                existing_data.get('lon'),
                existing_data.get('vertical_rate'),
                existing_data.get('squawk'),
                first_seen,
                last_seen,
                data_json
            ))
            await db.commit()
            return existing_data

    async def get_all_aircraft(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM aircraft ORDER BY last_seen DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
