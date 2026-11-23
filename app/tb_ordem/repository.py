"""Camada de acesso a dados do módulo de pedidos (pedido + status)."""

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.order_item.models import OrderItem
from app.tb_ordem.models import OrderStatus, tb_ordem
from app.usuarios.models import Usuario


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _consulta(self) -> Select:
        """Pedido já com status e itens (e o produto de cada item).

        `selectinload` nos itens (coleção) mantém o LIMIT correto na paginação;
        `joinedload` no status é seguro porque é muitos-para-um.
        """
        return select(tb_ordem).options(
            joinedload(tb_ordem.ordem_status),
            selectinload(tb_ordem.itens).selectinload(OrderItem.product),
        )

    # --- pedidos ---------------------------------------------------------------

    def listar(
        self,
        user_id: int | None = None,
        status_name: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[tb_ordem]:
        stmt = self._consulta()
        if user_id is not None:
            stmt = stmt.where(tb_ordem.user_id == user_id)
        if status_name is not None:
            stmt = stmt.where(tb_ordem.ordem_status.has(status_name=status_name))
        stmt = stmt.order_by(tb_ordem.order_id).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def buscar_por_id(self, order_id: int) -> tb_ordem | None:
        stmt = self._consulta().where(tb_ordem.order_id == order_id)
        return self.db.scalars(stmt).first()

    def usuario_existe(self, user_id: int) -> bool:
        """Checa direto na tabela de usuários. O SQLite não valida FK por
        padrão, então sem isso um pedido com user_id inventado seria gravado."""
        return self.db.get(Usuario, user_id) is not None

    def salvar(self, ordem: tb_ordem, commit: bool = True) -> tb_ordem:
        """`commit=False` só envia ao banco (flush): quem chamou confirma a
        transação, para operações "tudo ou nada"."""
        self.db.add(ordem)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        self.db.refresh(ordem)
        return ordem

    def deletar(self, ordem: tb_ordem) -> None:
        """Remove o pedido; os itens saem junto pela cascata do model."""
        self.db.delete(ordem)
        self.db.commit()

    # --- status (somente leitura) ----------------------------------------------

    def listar_status(self) -> list[OrderStatus]:
        stmt = select(OrderStatus).order_by(OrderStatus.order_status_id)
        return list(self.db.scalars(stmt).all())

    def buscar_status_por_nome(self, status_name: str) -> OrderStatus | None:
        stmt = select(OrderStatus).where(OrderStatus.status_name == status_name)
        return self.db.scalars(stmt).first()
