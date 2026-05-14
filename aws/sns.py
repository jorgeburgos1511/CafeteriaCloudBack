import boto3
import os

sns = boto3.client("sns")
TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")


def subscribe_email(email: str) -> None:
    if not TOPIC_ARN:
        return
    sns.subscribe(TopicArn=TOPIC_ARN, Protocol="email", Endpoint=email)


def publish_ticket(pedido: dict) -> None:
    if not TOPIC_ARN:
        return
    items_text = "\n".join(
        f"  - {item['producto_nombre']}: ${float(item['precio']):.2f} [{item['estado']}]"
        for item in pedido.get("items", [])
    )
    message = (
        f"Ticket de Pedido - Cafetería Universitaria\n"
        f"{'=' * 40}\n"
        f"Pedido #: {pedido['id'][:8].upper()}\n"
        f"Cliente: {pedido['cliente_nombre']}\n"
        f"Correo: {pedido['cliente_email']}\n"
        f"Fecha: {pedido['created_at']}\n\n"
        f"Productos:\n{items_text}\n\n"
        f"Total: ${float(pedido['total']):.2f}\n\n"
        f"¡Gracias por su compra!"
    )
    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject="Ticket de Pedido - Cafetería",
        Message=message,
    )
