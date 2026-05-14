from pydantic import BaseModel, Field
from uuid import uuid4
from typing import Literal, Optional

class ProductCreate(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    category: Literal["Comida", "Bebida"]
    available: bool = True

class ProductUpdate(BaseModel):
    name: str
    price: float = Field(..., gt=0)
    category: Literal["Comida", "Bebida"]
    available: bool = True

class Product(ProductCreate):
    id: str
    image_url: Optional[str] = None

    @staticmethod
    def create(data: ProductCreate):
        return Product(
            id=str(uuid4()),
            name=data.name,
            price=data.price,
            category=data.category,
            available=data.available,
            image_url=None,
        )