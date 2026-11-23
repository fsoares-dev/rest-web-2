"""Entidades do módulo de pedidos: `tb_ordem` e a tabela de status.

O `order_status` foi absorvido por este módulo: ele só tem leitura e o seu
conteúdo (os nomes) é definido pelo enum `StatusNome`, então não precisa de
pacote/router próprio.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.order_item.models import OrderItem


class StatusNome(str, Enum):
    PENDENTE = "Pendente"
    PAGO = "Pago"
    ENVIADO = "Enviado"
    CANCELADO = "Cancelado"
    ENTREGUE = "Entregue"


class OrderStatus(Base):
    __tablename__ = "ordem_status"

    order_status_id: Mapped[int] = mapped_column(primary_key=True)
    status_name: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str | None] = mapped_column(String(200), default=None)


class tb_ordem(Base):
    __tablename__ = "tabela_ordem"

    order_id: Mapped[int] = mapped_column(primary_key=True)
    total_value: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    number_nf: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey("tb_usuarios.usuario_id"))
    order_status_id: Mapped[int] = mapped_column(
        ForeignKey("ordem_status.order_status_id")
    )

    ordem_status: Mapped[OrderStatus] = relationship()
    # Apagar o pedido apaga os itens dele (sem mexer no estoque: ao cancelar,
    # a devolução já foi feita por restore_stock_for_order).
    itens: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def status(self) -> str:
        """Usado pelo OrderOut: devolve o nome do status, não o id."""
        return self.ordem_status.status_name
