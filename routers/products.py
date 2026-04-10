from fastapi import APIRouter, HTTPException, Query
from botocore.exceptions import ClientError
from decimal import Decimal
from schemas.product import ProductCreate, ProductUpdate, Product
from aws.dynamodb import products_table
from typing import Literal

router = APIRouter(prefix="/products", tags=["products"])


def serialize_product_for_dynamodb(product: Product) -> dict:
    data = product.model_dump()
    data["price"] = Decimal(str(data["price"]))
    return data


def deserialize_product_from_dynamodb(item: dict) -> dict:
    if "price" in item:
        item["price"] = float(item["price"])
    return item


@router.post("/", response_model=Product)
def create_product(product: ProductCreate):
    try:
        response = products_table.scan()
        products = response.get("Items", [])

        for existing_product in products:
            if existing_product["name"].lower() == product.name.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe un producto con ese nombre"
                )

        new_product = Product.create(product)

        products_table.put_item(Item=serialize_product_for_dynamodb(new_product))
        return new_product

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear producto: {str(e)}"
        )


@router.get("/", response_model=list[Product])
def get_products():
    try:
        response = products_table.scan()
        products = response.get("Items", [])
        return [deserialize_product_from_dynamodb(product) for product in products]

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener productos: {str(e)}"
        )


@router.get("/search/by-name", response_model=Product)
def get_product_by_name(name: str = Query(..., description="Nombre del producto")):
    try:
        response = products_table.scan()
        products = response.get("Items", [])

        for product in products:
            if product["name"].lower() == name.lower():
                return deserialize_product_from_dynamodb(product)

        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado"
        )

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar producto: {str(e)}"
        )


@router.get("/search/by-category", response_model=list[Product])
def get_products_by_category(
    category: Literal["Comida", "Bebida"] = Query(..., description="Categoría del producto")
):
    try:
        response = products_table.scan()
        products = response.get("Items", [])

        filtered_products = [
            deserialize_product_from_dynamodb(product)
            for product in products
            if product["category"] == category
        ]

        return filtered_products

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar productos por categoría: {str(e)}"
        )


@router.get("/{product_id}", response_model=Product)
def get_product_by_id(product_id: str):
    try:
        response = products_table.get_item(Key={"id": product_id})

        if "Item" not in response:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado"
            )

        return deserialize_product_from_dynamodb(response["Item"])

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener producto: {str(e)}"
        )


@router.put("/{product_id}", response_model=Product)
def update_product(product_id: str, product_data: ProductUpdate):
    try:
        existing = products_table.get_item(Key={"id": product_id})

        if "Item" not in existing:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado"
            )

        response = products_table.scan()
        products = response.get("Items", [])

        for product in products:
            if (
                product["name"].lower() == product_data.name.lower()
                and product["id"] != product_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe otro producto con ese nombre"
                )

        updated_product = Product(
            id=product_id,
            name=product_data.name,
            price=product_data.price,
            category=product_data.category,
            available=product_data.available
        )

        products_table.put_item(Item=serialize_product_for_dynamodb(updated_product))
        return updated_product

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar producto: {str(e)}"
        )


@router.delete("/{product_id}")
def delete_product(product_id: str):
    try:
        response = products_table.get_item(Key={"id": product_id})

        if "Item" not in response:
            raise HTTPException(
                status_code=404,
                detail="Producto no encontrado"
            )

        deleted_product = deserialize_product_from_dynamodb(response["Item"])

        products_table.delete_item(Key={"id": product_id})

        return {
            "message": "Producto eliminado correctamente",
            "product": deleted_product
        }

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar producto: {str(e)}"
        )