from fastapi import APIRouter, HTTPException
from botocore.exceptions import ClientError
from schemas.pedido import Pedido, PedidoCreate
from aws.dynamodb import pedidos_table

router = APIRouter(prefix="/pedidos", tags=["pedidos"])

ESTADOS = ["Recibido", "En preparación", "Listo", "Entregado"]


@router.post("/", response_model=Pedido)
def create_pedido(pedido: PedidoCreate):
    try:
        new_pedido = Pedido.create(pedido)
        pedidos_table.put_item(Item=new_pedido.model_dump())
        return new_pedido
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error al crear pedido: {str(e)}")


@router.get("/", response_model=list[Pedido])
def get_pedidos():
    try:
        response = pedidos_table.scan()
        return response.get("Items", [])
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener pedidos: {str(e)}")


@router.get("/{pedido_id}", response_model=Pedido)
def get_pedido(pedido_id: str):
    try:
        response = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        return response["Item"]
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener pedido: {str(e)}")


@router.patch("/{pedido_id}/avanzar", response_model=Pedido)
def avanzar_estado(pedido_id: str):
    try:
        response = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        pedido = response["Item"]
        estado_actual = pedido["estado"]

        if estado_actual not in ESTADOS or estado_actual == "Entregado":
            raise HTTPException(status_code=400, detail="El pedido ya está en su estado final")

        nuevo_estado = ESTADOS[ESTADOS.index(estado_actual) + 1]

        pedidos_table.update_item(
            Key={"id": pedido_id},
            UpdateExpression="SET estado = :e",
            ExpressionAttributeValues={":e": nuevo_estado},
        )

        pedido["estado"] = nuevo_estado
        return pedido
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error al avanzar estado: {str(e)}")


@router.patch("/{pedido_id}/cancelar", response_model=Pedido)
def cancelar_pedido(pedido_id: str):
    try:
        response = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        pedidos_table.update_item(
            Key={"id": pedido_id},
            UpdateExpression="SET estado = :e",
            ExpressionAttributeValues={":e": "Cancelado"},
        )

        pedido = response["Item"]
        pedido["estado"] = "Cancelado"
        return pedido
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error al cancelar pedido: {str(e)}")
