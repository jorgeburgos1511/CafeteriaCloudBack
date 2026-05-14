from pydantic import BaseModel, EmailStr
from uuid import uuid4
from typing import Optional

class CustomerCreate(BaseModel):
    name: str
    email: EmailStr

class CustomerUpdate(BaseModel):
    name: str
    email: EmailStr

class Customer(CustomerCreate):
    id: str
    sns_topic_arn: Optional[str] = None

    @staticmethod
    def create(data: CustomerCreate):
        return Customer(
            id=str(uuid4()),
            name=data.name,
            email=data.email,
            sns_topic_arn=None,
        )