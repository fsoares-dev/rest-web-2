"""Os DTOs (Pydantic) do módulo de pedidos."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.order_item.schemas import ItemOut
from app.tb_ordem.models import StatusNome


class OrderCreate(BaseModel):
    """DTO de entrada do POST /orders. O pedido nasce vazio, só precisa do
    usuário."""

    user_id: int


class OrderOut(BaseModel):
    """DTO de saída. Status por nome (não id), com os itens embutidos no mesmo
    formato do `GET /orders/{id}/items`."""

    model_config = ConfigDict(from_attributes=True)

    order_id: int
    total_value: Decimal
    number_nf: int | None
    created_at: datetime
    user_id: int
    status: str
    itens: list[ItemOut] = []


class StatusUpdate(BaseModel):
    """DTO de entrada do PATCH /orders/{id}/status."""

    status: StatusNome


class OrderStatusOut(BaseModel):
    """DTO de saída do GET /orders/statuses."""

    model_config = ConfigDict(from_attributes=True)

    order_status_id: int
    status_name: str
    description: str | None = None
