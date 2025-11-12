from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from database import create_document, get_documents

app = FastAPI(title="DealWise Backend", version="1.0.0")

# Open CORS for demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Provider adapters (mock-friendly)
AMAZON_KEYS_PRESENT = all([
    os.getenv("AMAZON_ACCESS_KEY"),
    os.getenv("AMAZON_SECRET_KEY"),
    os.getenv("AMAZON_PARTNER_TAG"),
])
FLIPKART_KEYS_PRESENT = all([
    os.getenv("FLIPKART_AFFILIATE_ID"),
    os.getenv("FLIPKART_AFFILIATE_TOKEN"),
])

async def fetch_amazon(query: str, limit: int) -> List[Dict[str, Any]]:
    if not AMAZON_KEYS_PRESENT:
        return [
            {
                "sku": f"AMZ-{i}",
                "title": f"Amazon mock item {i} for {query}",
                "image_url": "https://via.placeholder.com/200x200.png?text=Amazon",
                "url": "https://www.amazon.in/",
                "merchant": "amazon",
                "price": 999 + i * 10,
                "currency": "INR",
            }
            for i in range(1, limit + 1)
        ]
    # TODO: real Amazon integration when keys are provided
    return []

async def fetch_flipkart(query: str, limit: int) -> List[Dict[str, Any]]:
    if not FLIPKART_KEYS_PRESENT:
        return [
            {
                "sku": f"FK-{i}",
                "title": f"Flipkart mock item {i} for {query}",
                "image_url": "https://via.placeholder.com/200x200.png?text=Flipkart",
                "url": "https://www.flipkart.com/",
                "merchant": "flipkart",
                "price": 899 + i * 12,
                "currency": "INR",
            }
            for i in range(1, limit + 1)
        ]
    # TODO: real Flipkart integration when keys are provided
    return []

@app.get("/")
async def root():
    return {"ok": True, "service": "DealWise Backend"}

@app.get("/test")
async def test():
    # simple DB test
    try:
        docs = await get_documents("health", {}, limit=1)
        return {"ok": True, "db": True, "docs": docs}
    except Exception as e:
        return {"ok": True, "db": False, "error": str(e)}

@app.get("/providers")
async def providers():
    return {
        "providers": [
            {"name": "amazon", "enabled": AMAZON_KEYS_PRESENT},
            {"name": "flipkart", "enabled": FLIPKART_KEYS_PRESENT},
        ]
    }

@app.get("/search")
async def search(query: str = Query(...), limit: int = 10, providers: Optional[str] = None):
    prov_list = [p.strip().lower() for p in providers.split(",")] if providers else ["amazon", "flipkart"]
    results: List[Dict[str, Any]] = []
    if "amazon" in prov_list:
        results.extend(await fetch_amazon(query, limit))
    if "flipkart" in prov_list:
        results.extend(await fetch_flipkart(query, limit))

    # persist query and listings
    await create_document("searchquery", {"query": query, "providers": prov_list, "limit": limit})
    for r in results:
        await create_document("listings", r)
        await create_document("pricehistory", {
            "sku": r["sku"],
            "merchant": r["merchant"],
            "price": r["price"],
            "currency": r.get("currency", "INR"),
        })

    return {"results": results}

@app.get("/listings")
async def get_listings(sku: Optional[str] = None, merchant: Optional[str] = None, limit: int = 50):
    filt: Dict[str, Any] = {}
    if sku:
        filt["sku"] = sku
    if merchant:
        filt["merchant"] = merchant
    docs = await get_documents("listings", filt, limit)
    return docs

@app.get("/history/{merchant}/{sku}")
async def history(merchant: str, sku: str, limit: int = 100):
    docs = await get_documents("pricehistory", {"merchant": merchant, "sku": sku}, limit)
    return docs

class FavoriteIn(BaseModel):
    user_id: str
    sku: str
    title: str
    image_url: Optional[str] = None
    url: Optional[str] = None
    merchant: str
    price: float
    currency: str = "INR"

@app.post("/favorites")
async def add_favorite(fav: FavoriteIn):
    fav_id = await create_document("favorite", fav.model_dump())
    return {"ok": True, "id": fav_id}

@app.get("/favorites")
async def list_favorites(user_id: str):
    docs = await get_documents("favorite", {"user_id": user_id}, 200)
    return docs

@app.delete("/favorites/{fav_id}")
async def delete_favorite(fav_id: str):
    from bson import ObjectId
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    client = AsyncIOMotorClient(os.getenv("DATABASE_URL", "mongodb://localhost:27017"))
    db = client[os.getenv("DATABASE_NAME", "dealwise")]
    try:
        res = await db["favorite"].delete_one({"_id": ObjectId(fav_id)})
        return {"ok": True, "deleted": res.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
