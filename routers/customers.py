from fastapi import APIRouter, HTTPException, Query
from botocore.exceptions import ClientError
from schemas.customer import CustomerCreate, CustomerUpdate, Customer
from aws.dynamodb import customers_table

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/", response_model=Customer)
def create_customer(customer: CustomerCreate):
    # Validar duplicado por email
    response = customers_table.scan()
    customers = response.get("Items", [])

    for existing_customer in customers:
        if existing_customer["email"].lower() == customer.email.lower():
            raise HTTPException(
                status_code=400,
                detail="Ya existe un cliente con ese correo"
            )

    new_customer = Customer.create(customer)

    try:
        customers_table.put_item(Item=new_customer.model_dump())
        return new_customer
    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar cliente en DynamoDB: {str(e)}"
        )


@router.get("/", response_model=list[Customer])
def get_customers():
    try:
        response = customers_table.scan()
        return response.get("Items", [])
    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener clientes: {str(e)}"
        )


@router.get("/search/by-email", response_model=Customer)
def get_customer_by_email(email: str = Query(..., description="Correo del cliente")):
    try:
        response = customers_table.scan()
        customers = response.get("Items", [])

        for customer in customers:
            if customer["email"].lower() == email.lower():
                return customer

        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado"
        )

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar cliente por correo: {str(e)}"
        )


@router.get("/{customer_id}", response_model=Customer)
def get_customer_by_id(customer_id: str):
    try:
        response = customers_table.get_item(Key={"id": customer_id})

        if "Item" not in response:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )

        return response["Item"]

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al buscar cliente por id: {str(e)}"
        )


@router.put("/{customer_id}", response_model=Customer)
def update_customer(customer_id: str, customer_data: CustomerUpdate):
    try:
        # Verificar que exista el cliente
        existing_response = customers_table.get_item(Key={"id": customer_id})

        if "Item" not in existing_response:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )

        # Validar que no exista otro cliente con el mismo email
        scan_response = customers_table.scan()
        customers = scan_response.get("Items", [])

        for customer in customers:
            if (
                customer["email"].lower() == customer_data.email.lower()
                and customer["id"] != customer_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe otro cliente con ese correo"
                )

        updated_customer = Customer(
            id=customer_id,
            name=customer_data.name,
            email=customer_data.email
        )

        customers_table.put_item(Item=updated_customer.model_dump())
        return updated_customer

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar cliente: {str(e)}"
        )


@router.delete("/{customer_id}")
def delete_customer(customer_id: str):
    try:
        response = customers_table.get_item(Key={"id": customer_id})

        if "Item" not in response:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado"
            )

        deleted_customer = response["Item"]

        customers_table.delete_item(Key={"id": customer_id})

        return {
            "message": "Cliente eliminado correctamente",
            "customer": deleted_customer
        }

    except ClientError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar cliente: {str(e)}"
        )