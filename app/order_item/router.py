"""Controller do item de pedido — só traduz HTTP."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.order_item.schemas import ItemCreate, ItemOut, ItemUpdate
from app.order_item.services import OrderItemService
from app.tb_ordem.schemas import OrderOut
from app.usuarios.dependencies import get_current_user
from app.usuarios.models import Usuario

router = APIRouter(tags=["Itens de pedido"])


def get_service(db: Annotated[Session, Depends(get_db)]) -> OrderItemService:
    return OrderItemService(db)


Service = Annotated[OrderItemService, Depends(get_service)]


@router.get(
    "/orders/{order_id}/items",
    response_model=list[ItemOut],
    status_code=status.HTTP_200_OK,
)
def listar_itens(
    order_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.list_items(order_id)


@router.post(
    "/orders/{order_id}/items",
    response_model=ItemOut,
    status_code=status.HTTP_201_CREATED,
)
def adicionar_item(
    order_id: int,
    dados: ItemCreate,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.add_item(order_id, dados)


@router.patch(
    "/orders/{order_id}/items/{product_id}",
    response_model=ItemOut,
    status_code=status.HTTP_200_OK,
)
def atualizar_quantidade(
    order_id: int,
    product_id: int,
    dados: ItemUpdate,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.update_quantity(order_id, product_id, dados)


@router.delete(
    "/orders/{order_id}/items/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_item(
    order_id: int,
    product_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
) -> None:
    service.remove_item(order_id, product_id)


# Decisão do time: "fechar pedido" = status PAGO. Esta rota chama o
# change_status por baixo; não duplica a regra de transição.
@router.post(
    "/orders/{order_id}/close",
    response_model=OrderOut,
    status_code=status.HTTP_200_OK,
)
def fechar_pedido(
    order_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    return service.close_order(order_id)
