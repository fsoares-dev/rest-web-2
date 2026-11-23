"""Camada HTTP de `product`: recebe, delega ao service, devolve."""

from fastapi import APIRouter, Depends, Query, status

from app.database import DbSession
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.services.product import ProductService
from app.usuarios.dependencies import get_current_user
from app.usuarios.models import Usuario

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut], status_code=status.HTTP_200_OK)
def list_products(
    db: DbSession,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    category_id: int | None = Query(default=None),
    active: bool | None = Query(
        default=True, description="Por padrão lista só os ativos; use null para todos."
    ),
):
    return ProductService(db).list(
        skip=skip, limit=limit, category_id=category_id, active=active
    )


@router.get("/{product_id}", response_model=ProductOut, status_code=status.HTTP_200_OK)
def get_product(product_id: int, db: DbSession):
    return ProductService(db).get(product_id)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    db: DbSession,
    current_user: Usuario = Depends(get_current_user),
):
    return ProductService(db).create(data)


@router.patch(
    "/{product_id}", response_model=ProductOut, status_code=status.HTTP_200_OK
)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: DbSession,
    current_user: Usuario = Depends(get_current_user),
):
    return ProductService(db).update(product_id, data)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: DbSession,
    current_user: Usuario = Depends(get_current_user),
) -> None:
    """Apaga o produto. 409 se ele já estiver em algum pedido."""
    ProductService(db).delete(product_id)