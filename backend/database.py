import os
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

MONGO_URL = os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
DB_NAME = os.getenv("DATABASE_NAME") or "dealwise"

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

async def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db

async def create_document(collection: str, data: Dict[str, Any]) -> str:
    db = await get_db()
    doc = {**data, "created_at": __import__("datetime").datetime.utcnow()}
    res = await db[collection].insert_one(doc)
    return str(res.inserted_id)

async def get_documents(collection: str, filter_dict: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[Dict[str, Any]]:
    db = await get_db()
    filter_dict = filter_dict or {}
    cursor = db[collection].find(filter_dict).limit(limit)
    docs = []
    async for d in cursor:
        d["_id"] = str(d["_id"])
        docs.append(d)
    return docs
