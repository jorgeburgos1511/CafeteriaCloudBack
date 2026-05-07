import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")


def _create_table_if_not_exists(table_name: str, key_schema: list, attribute_definitions: list):
    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attribute_definitions,
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        print(f"Tabla '{table_name}' creada.")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"Tabla '{table_name}' ya existe.")
        else:
            raise


def init_tables():
    key_schema = [{"AttributeName": "id", "KeyType": "HASH"}]
    attr_def = [{"AttributeName": "id", "AttributeType": "S"}]
    _create_table_if_not_exists("customers", key_schema, attr_def)
    _create_table_if_not_exists("products", key_schema, attr_def)
    _create_table_if_not_exists("pedidos", key_schema, attr_def)


customers_table = dynamodb.Table("customers")
products_table = dynamodb.Table("products")
pedidos_table = dynamodb.Table("pedidos")