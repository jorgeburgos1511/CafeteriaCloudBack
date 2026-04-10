import boto3

dynamodb = boto3.resource("dynamodb")

customers_table = dynamodb.Table("customers")
products_table = dynamodb.Table("products")