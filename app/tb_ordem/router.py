"""O Controller do módulo de pedidos — ciclo de vida do pedido e seus status."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.tb_ordem.models import StatusNome
from app.tb_ordem.schemas import OrderCreate, OrderOut, OrderStatusOut, StatusUpdate
from app.tb_ordem.services import OrderService
from app.usuarios.dependencies import get_current_user
from app.usuarios.models import Usuario

router = APIRouter(tags=["Pedidos"])


def get_service(db: Annotated[Session, Depends(get_db)]) -> OrderService:
    return OrderService(db)


Service = Annotated[OrderService, Depends(get_service)]
Skip = Annotated[int, Query(ge=0, description="Quantos registros pular (offset).")]
Limit = Annotated[int, Query(ge=1, le=200, description="Máximo de registros.")]


# IMPORTANTE: /orders/statuses precisa vir ANTES de /orders/{order_id}, senão
# o FastAPI tentaria converter "statuses" em int e devolveria 422.
@router.get("/orders/statuses", response_model=list[OrderStatusOut])
def listar_status(service: Service):
    """Status possíveis de um pedido (somente leitura)."""
    return service.listar_status()


@router.get("/orders", response_model=list[OrderOut])
def listar_pedidos(
    service: Service,
    skip: Skip = 0,
    limit: Limit = 100,
    status_name: StatusNome | None = Query(default=None, alias="status"),
    current_user: Usuario = Depends(get_current_user),
):
    return service.listar(
        status_name=status_name.value if status_name else None,
        skip=skip,
        limit=limit,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
def buscar_pedido(
    order_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.buscar(order_id)


@router.get("/users/{user_id}/orders", response_model=list[OrderOut])
def listar_pedidos_do_usuario(
    user_id: int,
    service: Service,
    skip: Skip = 0,
    limit: Limit = 100,
    current_user: Usuario = Depends(get_current_user),
):
    return service.listar_por_usuario(user_id, skip=skip, limit=limit)


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def criar_pedido(
    dados: OrderCreate,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.criar(dados)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def mudar_status_pedido(
    order_id: int,
    dados: StatusUpdate,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.change_status(order_id, dados.status)


@router.patch("/orders/{order_id}/cancel", response_model=OrderOut)
def cancelar_pedido(
    order_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    """Atalho para cancelar: muda o status para Cancelado e devolve o estoque."""
    return service.cancel(order_id)


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_pedido(
    order_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
) -> None:
    """Apaga o pedido e seus itens. Só permitido para pedidos Cancelados."""
    service.delete(order_id)
