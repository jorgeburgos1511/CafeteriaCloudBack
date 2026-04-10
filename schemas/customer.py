from pydantic import BaseModel, EmailStr
from uuid import uuid4

class CustomerCreate(BaseModel):
    name: str
    email: EmailStr

class CustomerUpdate(BaseModel):
    name: str
    email: EmailStr

class Customer(CustomerCreate):
    id: str

    @staticmethod
    def create(data: CustomerCreate):
        return Customer(
            id=str(uuid4()),
            name=data.name,
            email=data.email
        )