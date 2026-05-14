from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv(override=True)
from fastapi.middleware.cors import CORSMiddleware
from routers.health import router as health_router
from routers.customers import router as customers_router
from routers.products import router as products_router
from routers.pedidos import router as pedidos_router
from routers.dashboard import router as dashboard_router
from aws.dynamodb import init_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tables()
    yield


app = FastAPI(title="Sistema de Pedidos Cafetería Universitaria", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(customers_router)
app.include_router(products_router)
app.include_router(pedidos_router)
app.include_router(dashboard_router)


@app.get("/", tags=["health"])
def root():
    return {"message": "API de cafetería activa"}