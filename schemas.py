"""
Database Schemas for DealWiseDe

Define MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Collection name is lowercase of class name.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Literal
from datetime import datetime

# Users who save favorites, simple profile for now
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    avatar_url: Optional[str] = None
    is_active: bool = True

# A single normalized product listing returned from a provider (amazon/flipkart/etc.)
class Listing(BaseModel):
    sku: str = Field(..., description="Stable identifier for product (provider SKU or ASIN)")
    title: str
    image_url: Optional[HttpUrl] = None
    url: Optional[HttpUrl] = None
    merchant: Literal["amazon", "flipkart", "other"] = "other"
    price: float = Field(..., ge=0)
    currency: str = Field("INR", description="ISO currency code")
    rating: Optional[float] = Field(None, ge=0, le=5)
    total_reviews: Optional[int] = Field(None, ge=0)
    availability: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

# Store price over time for a listing
class Pricehistory(BaseModel):
    sku: str
    merchant: str
    price: float = Field(..., ge=0)
    currency: str = Field("INR")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Saved user favorites
class Favorite(BaseModel):
    user_id: str
    sku: str
    title: str
    image_url: Optional[str] = None
    url: Optional[str] = None
    merchant: str
    price: float
    currency: str = "INR"
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Store search queries for analytics
class Searchquery(BaseModel):
    query: str
    user_id: Optional[str] = None
    providers: List[str] = ["amazon", "flipkart"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
