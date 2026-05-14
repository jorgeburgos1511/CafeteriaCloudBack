import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("pedidos")


def lambda_handler(event, context):
    scan = table.scan(ProjectionExpression="id")
    items = scan.get("Items", [])

    deleted = 0
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={"id": item["id"]})
            deleted += 1

    print(f"Reset semanal completado: {deleted} pedidos eliminados.")
    return {"deleted": deleted}
