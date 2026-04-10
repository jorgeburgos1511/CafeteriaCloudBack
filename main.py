from fastapi import FastAPI
from routers.health import router as health_router
from routers.customers import router as customers_router
from routers.products import router as products_router

app = FastAPI(title="Sistema de Pedidos Cafetería Universitaria")

app.include_router(health_router)
app.include_router(customers_router)
app.include_router(products_router)

@app.get("/", tags=["health"])
def root():
    return {"message": "API de cafetería activa"}