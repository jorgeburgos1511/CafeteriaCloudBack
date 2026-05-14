from fastapi import APIRouter, HTTPException
from botocore.exceptions import ClientError
from decimal import Decimal
from schemas.pedido import Pedido, PedidoCreate, AddItemRequest
from aws.dynamodb import pedidos_table, products_table
from aws.sns import subscribe_email, publish_ticket

router = APIRouter(prefix="/pedidos", tags=["pedidos"])

ESTADOS_ITEM = ["Recibido", "En preparación", "Listo", "Entregado"]


def _serialize(pedido: Pedido) -> dict:
    data = pedido.model_dump()
    data["total"] = Decimal(str(data["total"]))
    for item in data["items"]:
        item["precio"] = Decimal(str(item["precio"]))
    return data


def _deserialize(item: dict) -> dict:
    item["total"] = float(item.get("total", 0))
    for pi in item.get("items", []):
        pi["precio"] = float(pi["precio"])
    return item


@router.post("/", response_model=Pedido)
def create_pedido(data: PedidoCreate):
    try:
        pedido = Pedido.create(data)
        pedidos_table.put_item(Item=_serialize(pedido))
        try:
            subscribe_email(data.cliente_email)
        except Exception:
            pass
        return pedido
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[Pedido])
def get_pedidos():
    try:
        response = pedidos_table.scan()
        return [_deserialize(i) for i in response.get("Items", [])]
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{pedido_id}", response_model=Pedido)
def get_pedido(pedido_id: str):
    try:
        response = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        return _deserialize(response["Item"])
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{pedido_id}/items", response_model=Pedido)
def add_item(pedido_id: str, body: AddItemRequest):
    try:
        resp = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        pedido = _deserialize(resp["Item"])

        if pedido["estado"] != "Abierto":
            raise HTTPException(status_code=400, detail="El pedido ya está confirmado")

        prod_resp = products_table.get_item(Key={"id": body.producto_id})
        if "Item" not in prod_resp:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        producto = prod_resp["Item"]

        from uuid import uuid4
        new_item = {
            "item_id": str(uuid4()),
            "producto_id": body.producto_id,
            "producto_nombre": producto["name"],
            "precio": float(producto["price"]),
            "estado": "Recibido",
        }
        pedido["items"].append(new_item)
        pedido["total"] = sum(i["precio"] for i in pedido["items"])

        updated = Pedido(**pedido)
        pedidos_table.put_item(Item=_serialize(updated))
        return updated
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{pedido_id}/items/{item_id}", response_model=Pedido)
def remove_item(pedido_id: str, item_id: str):
    try:
        resp = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        pedido = _deserialize(resp["Item"])

        if pedido["estado"] != "Abierto":
            raise HTTPException(status_code=400, detail="El pedido ya está confirmado")

        original_len = len(pedido["items"])
        pedido["items"] = [i for i in pedido["items"] if i["item_id"] != item_id]
        if len(pedido["items"]) == original_len:
            raise HTTPException(status_code=404, detail="Item no encontrado")

        pedido["total"] = sum(i["precio"] for i in pedido["items"])
        updated = Pedido(**pedido)
        pedidos_table.put_item(Item=_serialize(updated))
        return updated
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{pedido_id}/confirmar", response_model=Pedido)
def confirmar_pedido(pedido_id: str):
    try:
        resp = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        pedido = _deserialize(resp["Item"])

        if pedido["estado"] != "Abierto":
            raise HTTPException(status_code=400, detail="El pedido no está en estado Abierto")
        if not pedido["items"]:
            raise HTTPException(status_code=400, detail="El pedido no tiene productos")

        pedido["estado"] = "Confirmado"
        updated = Pedido(**pedido)
        pedidos_table.put_item(Item=_serialize(updated))
        return updated
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{pedido_id}/items/{item_id}/avanzar", response_model=Pedido)
def avanzar_item(pedido_id: str, item_id: str):
    try:
        resp = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        pedido = _deserialize(resp["Item"])

        if pedido["estado"] not in ("Confirmado",):
            raise HTTPException(status_code=400, detail="El pedido debe estar Confirmado para avanzar items")

        item = next((i for i in pedido["items"] if i["item_id"] == item_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="Item no encontrado")
        if item["estado"] == "Entregado":
            raise HTTPException(status_code=400, detail="El item ya fue entregado")

        item["estado"] = ESTADOS_ITEM[ESTADOS_ITEM.index(item["estado"]) + 1]
        updated = Pedido(**pedido)
        pedidos_table.put_item(Item=_serialize(updated))
        return updated
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{pedido_id}/finalizar", response_model=Pedido)
def finalizar_pedido(pedido_id: str):
    try:
        resp = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        pedido = _deserialize(resp["Item"])

        if pedido["estado"] != "Confirmado":
            raise HTTPException(status_code=400, detail="El pedido debe estar Confirmado")
        if not pedido["items"]:
            raise HTTPException(status_code=400, detail="El pedido no tiene productos")
        if any(i["estado"] != "Entregado" for i in pedido["items"]):
            raise HTTPException(status_code=400, detail="Todos los productos deben estar Entregados")

        pedido["estado"] = "Finalizado"
        updated = Pedido(**pedido)
        pedidos_table.put_item(Item=_serialize(updated))

        try:
            publish_ticket(pedido)
        except Exception:
            pass

        return updated
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{pedido_id}/cancelar", response_model=Pedido)
def cancelar_pedido(pedido_id: str):
    try:
        resp = pedidos_table.get_item(Key={"id": pedido_id})
        if "Item" not in resp:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        pedido = _deserialize(resp["Item"])

        if pedido["estado"] in ("Finalizado", "Cancelado"):
            raise HTTPException(status_code=400, detail="El pedido ya está en estado final")

        pedido["estado"] = "Cancelado"
        updated = Pedido(**pedido)
        pedidos_table.put_item(Item=_serialize(updated))
        return updated
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))
