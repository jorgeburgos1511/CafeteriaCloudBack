from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import os, json, httpx
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from botocore.exceptions import ClientError
from aws.dynamodb import customers_table, products_table, pedidos_table
from schemas.customer import CustomerCreate, Customer
from schemas.product import ProductCreate, Product
from aws.sns import create_client_topic, publish_ticket
from aws.pdf import generate_ticket_pdf
from aws.s3 import upload_ticket_pdf

router = APIRouter(prefix="/chat", tags=["chat"])

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT_BASE = """Eres CaféBot, el asistente virtual de la Cafetería Universitaria ITESO.
Al inicio de cada conversación tienes acceso al MENÚ ACTUAL y a los CLIENTES REGISTRADOS (ver abajo).

Puedes ayudar con:
- Responder sobre el menú, precios y categorías (usa los datos del MENÚ ACTUAL)
- Registrar nuevos clientes con nombre y correo
- Agregar productos nuevos al menú (nombre, precio, categoría: Comida o Bebida)
- Crear notas de venta completas (genera PDF y envía ticket por correo al cliente)
- Explicar el flujo de pedidos: Abierto → Confirmado → items avanzan → Finalizado

FLUJO PARA REGISTRAR UN CLIENTE:
1. Pide nombre si no lo tienes.
2. Pide correo si no lo tienes.
3. Con ambos datos, llama a create_client.

FLUJO PARA AGREGAR UN PRODUCTO AL MENÚ:
1. Pide nombre si no lo tienes.
2. Pide precio si no lo tienes.
3. Pide categoría (Comida o Bebida) si no la tienes.
4. Con los 3 datos, llama a create_product.

FLUJO PARA CREAR UNA NOTA DE VENTA:
1. Pregunta el correo del cliente. Busca en CLIENTES REGISTRADOS para ayudar.
2. Pregunta qué productos quiere. Usa el MENÚ ACTUAL para sugerir opciones.
3. Conforme el usuario elija productos, menciona el carrito acumulado: "Carrito: X, Y, Z — Total estimado: $N".
4. Cuando el usuario confirme, llama a create_full_order con correo y lista de nombres exactos del menú.
   La herramienta crea el pedido, genera el PDF y envía el correo automáticamente.

Responde siempre en español, de forma amable y concisa."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_client",
            "description": "Registra un nuevo cliente en la cafetería con nombre y correo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre completo del cliente"},
                    "email": {"type": "string", "description": "Correo electrónico del cliente"},
                },
                "required": ["name", "email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product",
            "description": "Crea un nuevo producto en el menú de la cafetería.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nombre del producto"},
                    "price": {"type": "number", "description": "Precio en pesos"},
                    "category": {
                        "type": "string",
                        "enum": ["Comida", "Bebida"],
                        "description": "Categoría: Comida o Bebida",
                    },
                },
                "required": ["name", "price", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_full_order",
            "description": (
                "Crea una nota de venta completa para un cliente con los productos indicados. "
                "Genera el ticket PDF, lo sube a S3 y envía el correo al cliente por SNS. "
                "Usa los nombres exactos de los productos tal como aparecen en el MENÚ ACTUAL del contexto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_email": {
                        "type": "string",
                        "description": "Correo del cliente",
                    },
                    "producto_nombres": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de nombres exactos de productos a incluir en la orden",
                    },
                },
                "required": ["cliente_email", "producto_nombres"],
            },
        },
    },
]


# ── Ejecutores ──────────────────────────────────────────────────────────────

def _execute_create_client(name: str, email: str) -> str:
    try:
        for existing in customers_table.scan().get("Items", []):
            if existing["email"].lower() == email.lower():
                return f"Ya existe un cliente registrado con el correo {email}."
        new_customer = Customer.create(CustomerCreate(name=name, email=email))
        customers_table.put_item(Item=new_customer.model_dump())
        try:
            topic_arn = create_client_topic(new_customer.id, new_customer.email)
            customers_table.update_item(
                Key={"id": new_customer.id},
                UpdateExpression="SET sns_topic_arn = :a",
                ExpressionAttributeValues={":a": topic_arn},
            )
        except Exception:
            pass
        return f"OK: cliente '{name}' registrado con correo {email}."
    except ClientError as e:
        return f"Error de base de datos: {str(e)}"


def _execute_list_clients(busqueda: str = "") -> str:
    try:
        clients = customers_table.scan().get("Items", [])
        if busqueda:
            q = busqueda.lower()
            clients = [c for c in clients if q in c["name"].lower() or q in c["email"].lower()]
        if not clients:
            return "No hay clientes registrados todavía." if not busqueda else f"No se encontró ningún cliente con '{busqueda}'."
        lines = [f"- {c['name']} ({c['email']})" for c in clients[:20]]
        suffix = f"\n...y {len(clients) - 20} más." if len(clients) > 20 else ""
        return f"Clientes registrados ({len(clients)}):\n" + "\n".join(lines) + suffix
    except ClientError as e:
        return f"Error al obtener clientes: {str(e)}"


def _execute_create_product(name: str, price: float, category: str) -> str:
    try:
        for existing in products_table.scan().get("Items", []):
            if existing["name"].lower() == name.lower():
                return f"Ya existe un producto con el nombre '{name}'."
        new_product = Product.create(ProductCreate(name=name, price=price, category=category))
        data = new_product.model_dump()
        data["price"] = Decimal(str(data["price"]))
        products_table.put_item(Item=data)
        return f"OK: producto '{name}' creado — ${price:.2f} ({category})."
    except ClientError as e:
        return f"Error de base de datos: {str(e)}"


def _execute_list_products(categoria: str = "Todas") -> str:
    try:
        products = products_table.scan().get("Items", [])
        if categoria and categoria != "Todas":
            products = [p for p in products if p.get("category") == categoria]
        if not products:
            return "No hay productos en el menú todavía."
        lines = []
        for p in sorted(products, key=lambda x: x.get("category", "")):
            disp = "✓" if p.get("available", True) else "✗"
            lines.append(f"- {p['name']} | ${float(p['price']):.2f} | {p['category']} {disp}")
        return "Menú actual:\n" + "\n".join(lines)
    except ClientError as e:
        return f"Error al obtener productos: {str(e)}"


def _execute_get_product_by_name(name: str) -> str:
    try:
        for p in products_table.scan().get("Items", []):
            if p["name"].lower() == name.lower():
                disp = "Disponible" if p.get("available", True) else "No disponible"
                return (
                    f"Producto encontrado:\n"
                    f"  Nombre: {p['name']}\n"
                    f"  Precio: ${float(p['price']):.2f}\n"
                    f"  Categoría: {p['category']}\n"
                    f"  Estado: {disp}"
                )
        return f"No se encontró ningún producto con el nombre '{name}'."
    except ClientError as e:
        return f"Error al buscar producto: {str(e)}"


def _execute_create_full_order(cliente_email: str, producto_nombres: list) -> str:
    try:
        # 1. Buscar cliente
        customer = None
        for c in customers_table.scan().get("Items", []):
            if c["email"].lower() == cliente_email.lower():
                customer = c
                break
        if not customer:
            return f"No se encontró cliente con correo '{cliente_email}'. Regístralo primero con create_client."

        # 2. Resolver nombres de productos a registros reales
        all_products = {p["name"].lower(): p for p in products_table.scan().get("Items", [])}
        items = []
        not_found = []
        for nombre in producto_nombres:
            prod = all_products.get(nombre.lower())
            if prod:
                items.append({
                    "item_id": str(uuid4()),
                    "producto_id": prod["id"],
                    "producto_nombre": prod["name"],
                    "precio": float(prod["price"]),
                    "estado": "Entregado",
                })
            else:
                not_found.append(nombre)

        if not items:
            return (
                f"No se encontró ninguno de los productos indicados: {', '.join(producto_nombres)}.\n"
                "Usa list_products para ver los nombres exactos del menú."
            )

        total = sum(i["precio"] for i in items)
        pedido_id = str(uuid4())

        pedido = {
            "id": pedido_id,
            "cliente_nombre": customer["name"],
            "cliente_email": customer["email"],
            "cliente_sns_arn": customer.get("sns_topic_arn"),
            "estado": "Finalizado",
            "items": items,
            "total": total,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 3. Guardar en DynamoDB (Decimal para precios)
        pedido_db = {**pedido, "total": Decimal(str(total))}
        pedido_db["items"] = [
            {**item, "precio": Decimal(str(item["precio"]))} for item in items
        ]
        pedidos_table.put_item(Item=pedido_db)

        # 4. Generar PDF + subir S3 + enviar SNS
        ticket_msg = ""
        try:
            pdf_bytes = generate_ticket_pdf(pedido)
            pdf_url = upload_ticket_pdf(pedido_id, pdf_bytes)
            publish_ticket(pedido, pdf_url)
            ticket_msg = f"Ticket PDF generado y enviado por correo a {customer['email']}."
        except Exception as e:
            ticket_msg = f"Nota creada, pero no se pudo enviar el ticket: {e}"

        aviso = f"\n⚠️ No encontrados en el menú: {', '.join(not_found)}." if not_found else ""
        items_txt = "\n".join(f"  • {i['producto_nombre']}: ${i['precio']:.2f}" for i in items)

        return (
            f"✅ Nota de venta generada exitosamente.\n"
            f"  Cliente: {customer['name']} ({customer['email']})\n"
            f"  Productos:\n{items_txt}\n"
            f"  Total: ${total:.2f}\n"
            f"  {ticket_msg}"
            f"{aviso}"
        )

    except ClientError as e:
        return f"Error de base de datos: {str(e)}"


TOOL_EXECUTORS = {
    "create_client":     lambda a: _execute_create_client(a["name"], a["email"]),
    "create_product":    lambda a: _execute_create_product(a["name"], a["price"], a["category"]),
    "create_full_order": lambda a: _execute_create_full_order(a["cliente_email"], a["producto_nombres"]),
}


def _build_system_prompt() -> str:
    """Inyecta menú actual y clientes en el system prompt para que el bot responda sin tool calls."""
    lines = [SYSTEM_PROMPT_BASE]
    try:
        products = products_table.scan().get("Items", [])
        if products:
            menu = "\n".join(
                f"  - {p['name']}: ${float(p['price']):.2f} ({p['category']})"
                for p in sorted(products, key=lambda x: x.get("category", ""))
            )
            lines.append(f"\nMENÚ ACTUAL:\n{menu}")
        else:
            lines.append("\nMENÚ ACTUAL: (sin productos registrados aún)")
    except Exception:
        lines.append("\nMENÚ ACTUAL: (no disponible)")

    try:
        clients = customers_table.scan().get("Items", [])
        if clients:
            client_list = "\n".join(f"  - {c['name']} | {c['email']}" for c in clients[:30])
            lines.append(f"\nCLIENTES REGISTRADOS:\n{client_list}")
        else:
            lines.append("\nCLIENTES REGISTRADOS: (ninguno registrado aún)")
    except Exception:
        lines.append("\nCLIENTES REGISTRADOS: (no disponible)")

    return "\n".join(lines)


# ── Modelos ─────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []


# ── Groq helper ──────────────────────────────────────────────────────────────

def _groq_call(api_key: str, messages: list, use_tools: bool) -> dict:
    payload = {"model": MODEL, "messages": messages, "max_tokens": 600}
    if use_tools:
        payload["tools"] = TOOLS
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    if not res.is_success:
        raise HTTPException(status_code=503, detail=f"Error de Groq: {res.status_code} — {res.text}")
    return res.json()


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/")
def chat(req: ChatRequest):
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY no configurada")

    messages = [{"role": "system", "content": _build_system_prompt()}]
    for msg in req.history[-10:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})

    data = _groq_call(api_key, messages, use_tools=True)
    choice = data["choices"][0]
    assistant_msg = choice["message"]

    if choice.get("finish_reason") == "tool_calls" and assistant_msg.get("tool_calls"):
        messages.append(assistant_msg)

        for tool_call in assistant_msg["tool_calls"]:
            func_name = tool_call["function"]["name"]
            func_args = json.loads(tool_call["function"]["arguments"])
            executor = TOOL_EXECUTORS.get(func_name)
            result = executor(func_args) if executor else f"Función desconocida: {func_name}"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

        data2 = _groq_call(api_key, messages, use_tools=False)
        reply = data2["choices"][0]["message"]["content"]
    else:
        reply = assistant_msg.get("content", "")

    return {"response": reply}
