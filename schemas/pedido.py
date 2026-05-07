from pydantic import BaseModel
from uuid import uuid4
from typing import Literal, Optional
from datetime import datetime, timezone

EstadoPedido = Literal["Recibido", "En preparación", "Listo", "Entregado", "Cancelado"]


class PedidoCreate(BaseModel):
    cliente: str
    producto: str
    nota: Optional[str] = None


class Pedido(BaseModel):
    id: str
    cliente: str
    producto: str
    estado: EstadoPedido
    nota: Optional[str] = None
    created_at: str

    @staticmethod
    def create(data: PedidoCreate) -> "Pedido":
        return Pedido(
            id=str(uuid4()),
            cliente=data.cliente,
            producto=data.producto,
            estado="Recibido",
            nota=data.nota,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
