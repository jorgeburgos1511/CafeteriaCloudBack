from fastapi import APIRouter, HTTPException
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta
from aws.dynamodb import customers_table, pedidos_table

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/")
def get_dashboard():
    try:
        pedidos_resp = pedidos_table.scan()
        pedidos = pedidos_resp.get("Items", [])

        customers_resp = customers_table.scan()
        total_clientes = len(customers_resp.get("Items", []))

        today = datetime.now(timezone.utc).date()

        pedidos_hoy = sum(
            1 for p in pedidos
            if p.get("created_at", "").startswith(str(today))
        )
        ordenes_completadas = sum(1 for p in pedidos if p.get("estado") == "Finalizado")

        en_preparacion = sum(
            1 for p in pedidos
            for item in p.get("items", [])
            if item.get("estado") == "En preparación"
        )
        listos = sum(
            1 for p in pedidos
            for item in p.get("items", [])
            if item.get("estado") == "Listo"
        )

        actividad = sorted(pedidos, key=lambda p: p.get("created_at", ""), reverse=True)[:5]
        actividad_reciente = [
            f"Pedido de {p.get('cliente_nombre', p.get('cliente', 'Desconocido'))} — {p.get('estado', '')}"
            for p in actividad
        ]

        dias = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
        conteo = {str(d): 0 for d in dias}
        for p in pedidos:
            fecha = p.get("created_at", "")[:10]
            if fecha in conteo:
                conteo[fecha] += 1

        pedidos_por_dia = [
            {"dia": d.strftime("%d/%m"), "pedidos": conteo[str(d)]}
            for d in dias
        ]

        return {
            "pedidos_hoy": pedidos_hoy,
            "en_preparacion": en_preparacion,
            "listos": listos,
            "total_clientes": total_clientes,
            "ordenes_completadas": ordenes_completadas,
            "actividad_reciente": actividad_reciente,
            "pedidos_por_dia": pedidos_por_dia,
        }
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener dashboard: {str(e)}")
