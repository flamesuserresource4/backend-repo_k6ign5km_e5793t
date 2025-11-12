import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents

app = FastAPI(title="DealWiseDe API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# Utilities
# -------------------------------

def serialize_mongo(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id") is not None:
        d["_id"] = str(d["_id"])
    # Convert datetimes to isoformat
    for k, v in list(d.items()):
        if hasattr(v, "isoformat"):
            try:
                d[k] = v.isoformat()
            except Exception:
                pass
    return d


# -------------------------------
# Provider adapters (mock-friendly)
# -------------------------------

class ProviderResult(BaseModel):
    sku: str
    title: str
    image_url: Optional[str] = None
    url: Optional[str] = None
    merchant: str
    price: float
    currency: str = "INR"
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    availability: Optional[str] = None


def has_amazon_keys() -> bool:
    return bool(os.getenv("AMAZON_ACCESS_KEY") and os.getenv("AMAZON_SECRET_KEY") and os.getenv("AMAZON_PARTNER_TAG"))


def has_flipkart_keys() -> bool:
    # Flipkart Affiliate API uses token
    return bool(os.getenv("FLIPKART_AFFILIATE_ID") and os.getenv("FLIPKART_AFFILIATE_TOKEN"))


def fetch_amazon(query: str, limit: int = 5) -> List[ProviderResult]:
    # NOTE: Real Amazon Product Advertising API requires signed requests.
    # Here we return mock/demo data if keys are not configured to keep the app functional.
    if not has_amazon_keys():
        seed = [
            {
                "sku": f"AMZ-{i}",
                "title": f"{query.title()} - Amazon Variant {i}",
                "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?q=80&w=600",
                "url": "https://www.amazon.in/",
                "merchant": "amazon",
                "price": round(999 + i * 50.5, 2),
                "currency": "INR",
                "rating": 4.2,
                "total_reviews": 1200 + i * 15,
                "availability": "In Stock",
            }
            for i in range(1, limit + 1)
        ]
        return [ProviderResult(**s) for s in seed]

    # Placeholder for real integration
    # Implement PA-API v5 signed request here if keys exist. For now, return empty list.
    return []


def fetch_flipkart(query: str, limit: int = 5) -> List[ProviderResult]:
    if not has_flipkart_keys():
        seed = [
            {
                "sku": f"FK-{i}",
                "title": f"{query.title()} - Flipkart Variant {i}",
                "image_url": "https://images.unsplash.com/photo-1516387938699-a93567ec168e?q=80&w=600",
                "url": "https://www.flipkart.com/",
                "merchant": "flipkart",
                "price": round(979 + i * 48.3, 2),
                "currency": "INR",
                "rating": 4.1,
                "total_reviews": 900 + i * 25,
                "availability": "In Stock",
            }
            for i in range(1, limit + 1)
        ]
        return [ProviderResult(**s) for s in seed]

    # Placeholder if keys exist; not implemented in this environment
    return []


# -------------------------------
# API Schemas
# -------------------------------

class SearchResponse(BaseModel):
    query: str
    providers: List[str]
    results: List[ProviderResult]


class FavoriteIn(BaseModel):
    user_id: str
    sku: str
    title: str
    image_url: Optional[str] = None
    url: Optional[str] = None
    merchant: str
    price: float
    currency: str = "INR"


# -------------------------------
# Routes
# -------------------------------

@app.get("/")
def read_root():
    return {"message": "DealWiseDe backend running"}


@app.get("/providers")
def providers_status():
    return {
        "amazon": {
            "configured": has_amazon_keys(),
        },
        "flipkart": {
            "configured": has_flipkart_keys(),
        },
    }


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.get("/search", response_model=SearchResponse)
def search_products(q: str = Query(..., alias="query"), limit: int = 5, providers: Optional[str] = None):
    provider_list = [p.strip().lower() for p in (providers.split(",") if providers else ["amazon", "flipkart"]) if p.strip()]

    all_results: List[ProviderResult] = []
    if "amazon" in provider_list:
        all_results.extend(fetch_amazon(q, limit))
    if "flipkart" in provider_list:
        all_results.extend(fetch_flipkart(q, limit))

    # Persist listings and price history
    now = datetime.now(timezone.utc)
    for item in all_results:
        listing_doc = {
            "sku": item.sku,
            "title": item.title,
            "image_url": item.image_url,
            "url": item.url,
            "merchant": item.merchant,
            "price": item.price,
            "currency": item.currency,
            "rating": item.rating,
            "total_reviews": item.total_reviews,
            "availability": item.availability,
            "fetched_at": now,
        }
        try:
            create_document("listing", listing_doc)
        except Exception:
            pass
        try:
            create_document(
                "pricehistory",
                {
                    "sku": item.sku,
                    "merchant": item.merchant,
                    "price": item.price,
                    "currency": item.currency,
                    "timestamp": now,
                },
            )
        except Exception:
            pass

    # Save search query for analytics
    try:
        create_document(
            "searchquery",
            {"query": q, "providers": provider_list, "created_at": now},
        )
    except Exception:
        pass

    return SearchResponse(query=q, providers=provider_list, results=all_results)


@app.get("/history/{merchant}/{sku}")
def price_history(merchant: str, sku: str, limit: int = 50):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = (
        db["pricehistory"]
        .find({"merchant": merchant, "sku": sku})
        .sort("timestamp", -1)
        .limit(limit)
    )
    return [serialize_mongo(d) for d in docs]


@app.get("/listings")
def get_listings(sku: Optional[str] = None, merchant: Optional[str] = None, limit: int = 50):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    filt: Dict[str, Any] = {}
    if sku:
        filt["sku"] = sku
    if merchant:
        filt["merchant"] = merchant
    docs = db["listing"].find(filt).sort("fetched_at", -1).limit(limit)
    return [serialize_mongo(d) for d in docs]


@app.post("/favorites")
def add_favorite(payload: FavoriteIn):
    doc = payload.model_dump()
    try:
        inserted_id = create_document("favorite", {**doc, "created_at": datetime.now(timezone.utc)})
        return {"ok": True, "id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/favorites")
def list_favorites(user_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    items = db["favorite"].find({"user_id": user_id}).sort("created_at", -1)
    return [serialize_mongo(i) for i in items]


@app.delete("/favorites/{fav_id}")
def delete_favorite(fav_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from bson import ObjectId

    try:
        result = db["favorite"].delete_one({"_id": ObjectId(fav_id)})
        return {"ok": result.deleted_count == 1}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
