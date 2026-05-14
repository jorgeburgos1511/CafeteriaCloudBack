from pydantic import BaseModel, Field
from uuid import uuid4
from typing import Literal, List
from datetime import datetime, timezone

EstadoItem = Literal["Recibido", "En preparación", "Listo", "Entregado"]
EstadoPedido = Literal["Abierto", "Confirmado", "Finalizado", "Cancelado"]


class PedidoItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    producto_id: str
    producto_nombre: str
    precio: float
    estado: EstadoItem = "Recibido"


class PedidoCreate(BaseModel):
    cliente_nombre: str
    cliente_email: str


class AddItemRequest(BaseModel):
    producto_id: str


class Pedido(BaseModel):
    id: str
    cliente_nombre: str
    cliente_email: str
    estado: EstadoPedido
    items: List[PedidoItem] = []
    total: float = 0.0
    created_at: str

    @staticmethod
    def create(data: PedidoCreate) -> "Pedido":
        return Pedido(
            id=str(uuid4()),
            cliente_nombre=data.cliente_nombre,
            cliente_email=data.cliente_email,
            estado="Abierto",
            items=[],
            total=0.0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
