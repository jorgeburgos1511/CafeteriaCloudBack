import boto3
import os
import re

sns = boto3.client("sns")


def create_client_topic(client_id: str, email: str) -> str:
    safe_id = re.sub(r'[^a-zA-Z0-9-_]', '-', client_id)[:80]
    topic_name = f"cafeteria-cliente-{safe_id}"
    response = sns.create_topic(Name=topic_name)
    topic_arn = response["TopicArn"]
    sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
    return topic_arn


def publish_ticket(pedido: dict, pdf_url: str) -> None:
    topic_arn = pedido.get("cliente_sns_arn", "")
    if not topic_arn:
        return

    items_text = "\n".join(
        f"  - {item['producto_nombre']}: ${float(item['precio']):.2f}"
        for item in pedido.get("items", [])
    )

    message = (
        f"Ticket de Pedido - Cafeteria Universitaria\n"
        f"{'=' * 42}\n"
        f"Pedido #: {pedido['id'][:8].upper()}\n"
        f"Cliente:  {pedido['cliente_nombre']}\n"
        f"Correo:   {pedido['cliente_email']}\n\n"
        f"Productos:\n{items_text}\n\n"
        f"Total: ${float(pedido['total']):.2f}\n\n"
        f"Descarga tu ticket en PDF aqui (valido 7 dias):\n{pdf_url}\n\n"
        f"Gracias por su compra."
    )

    sns.publish(
        TopicArn=topic_arn,
        Subject=f"Ticket de Pedido #{pedido['id'][:8].upper()} - Cafeteria",
        Message=message,
    )
