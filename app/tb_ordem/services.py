"""Regras de negócio do módulo de pedidos (ciclo de vida + status)."""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.tb_ordem.models import OrderStatus, StatusNome, tb_ordem
from app.tb_ordem.repository import OrderRepository
from app.tb_ordem.schemas import OrderCreate

# Transições permitidas a partir de cada status atual.
TRANSICOES_PERMITIDAS: dict[StatusNome, list[StatusNome]] = {
    StatusNome.PENDENTE: [StatusNome.PAGO, StatusNome.CANCELADO],
    StatusNome.PAGO: [StatusNome.ENVIADO, StatusNome.CANCELADO],
    StatusNome.ENVIADO: [StatusNome.ENTREGUE],
    StatusNome.CANCELADO: [],
    StatusNome.ENTREGUE: [],
}


def transicao_valida(atual: StatusNome, novo: StatusNome) -> bool:
    return novo in TRANSICOES_PERMITIDAS.get(atual, [])


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OrderRepository(db)

    # --- leitura --------------------------------------------------------------

    def listar_status(self) -> list[OrderStatus]:
        return self.repo.listar_status()

    def listar(
        self,
        user_id: int | None = None,
        status_name: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[tb_ordem]:
        return self.repo.listar(
            user_id=user_id, status_name=status_name, skip=skip, limit=limit
        )

    def listar_por_usuario(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> list[tb_ordem]:
        """GET /users/{id}/orders: usuário que não existe é 404, não lista vazia."""
        if not self.repo.usuario_existe(user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuário {user_id} não encontrado.",
            )
        return self.repo.listar(user_id=user_id, skip=skip, limit=limit)

    def buscar(self, order_id: int) -> tb_ordem:
        ordem = self.repo.buscar_por_id(order_id)
        if ordem is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pedido {order_id} não encontrado.",
            )
        return ordem

    # --- criação --------------------------------------------------------------

    def criar(self, dados: OrderCreate) -> tb_ordem:
        if not self.repo.usuario_existe(dados.user_id):
            raise HTTPException(
                status_code=422,
                detail=f"Usuário {dados.user_id} não existe.",
            )

        status_inicial = self._status_cadastrado(StatusNome.PENDENTE)
        nova_ordem = tb_ordem(
            user_id=dados.user_id,
            order_status_id=status_inicial.order_status_id,
            total_value=Decimal("0.00"),
        )
        return self.repo.salvar(nova_ordem)

    # --- ciclo de vida --------------------------------------------------------

    def change_status(self, order_id: int, novo_status: StatusNome) -> tb_ordem:
        """Único ponto de entrada para mudar o status de um pedido.

        Cancelar SEMPRE passa por `cancel`, senão o PATCH /orders/{id}/status
        com "Cancelado" mudaria o status sem devolver o estoque dos itens.
        """
        if novo_status == StatusNome.CANCELADO:
            return self.cancel(order_id)
        return self._aplicar_status(self.buscar(order_id), novo_status)

    def cancel(self, order_id: int) -> tb_ordem:
        """Cancela o pedido e devolve ao estoque cada item dele.

        Tudo ou nada: a devolução do estoque e a mudança de status entram na
        MESMA transação. Se qualquer passo falhar, nada é gravado — não existe
        o caso "estoque devolvido, mas pedido ainda ativo" (que permitiria
        cancelar de novo e devolver em dobro).
        """
        ordem = self.buscar(order_id)
        # Valida antes de mexer no estoque: cancelar pedido Entregue dá 409.
        self._validar_transicao(ordem, StatusNome.CANCELADO)

        # Import tardio: order_item.services importa este módulo, e um import
        # no topo criaria um ciclo.
        from app.order_item.services import OrderItemService

        try:
            OrderItemService(self.db).restore_stock_for_order(order_id)
            self._aplicar_status(ordem, StatusNome.CANCELADO, commit=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.buscar(order_id)

    def delete(self, order_id: int) -> None:
        """Apaga um pedido, mas só se ele estiver Cancelado.

        Pedido ativo ou concluído é histórico financeiro e não se apaga.
        O estoque não é tocado aqui: ele já voltou quando o pedido foi
        cancelado, e devolver de novo contaria em dobro.
        """
        ordem = self.buscar(order_id)
        atual = StatusNome(ordem.ordem_status.status_name)
        if atual != StatusNome.CANCELADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Só pedidos '{StatusNome.CANCELADO.value}' podem ser "
                    f"apagados (status atual: '{atual.value}')."
                ),
            )
        self.repo.deletar(ordem)

    def recalculate_total(self, order_id: int, commit: bool = True) -> tb_ordem:
        """Soma quantity * price de cada item. `commit=False` deixa a
        transação aberta para o chamador (usado pelo módulo de itens)."""
        ordem = self.buscar(order_id)
        # Recarrega os itens do banco: a coleção já carregada na sessão pode
        # estar velha se o item foi gravado direto (sem passar pela relação).
        self.db.refresh(ordem, ["itens"])
        ordem.total_value = sum(
            (item.quantity * item.price for item in ordem.itens),
            Decimal("0.00"),
        )
        return self.repo.salvar(ordem, commit=commit)

    # --- internos -------------------------------------------------------------

    def _status_cadastrado(self, nome: StatusNome) -> OrderStatus:
        linha = self.repo.buscar_status_por_nome(nome.value)
        if linha is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Status '{nome.value}' não está cadastrado — rode o seed antes.",
            )
        return linha

    def _validar_transicao(self, ordem: tb_ordem, novo_status: StatusNome) -> StatusNome:
        atual = StatusNome(ordem.ordem_status.status_name)
        if not transicao_valida(atual, novo_status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transição de '{atual.value}' para '{novo_status.value}' não é permitida.",
            )
        return atual

    def _aplicar_status(
        self, ordem: tb_ordem, novo_status: StatusNome, commit: bool = True
    ) -> tb_ordem:
        self._validar_transicao(ordem, novo_status)

        # Pagar (= fechar) exige item: vale também para o PATCH, não só para o
        # POST /orders/{id}/close.
        if novo_status == StatusNome.PAGO and not ordem.itens:
            raise HTTPException(
                status_code=422,
                detail=f"Pedido {ordem.order_id} não tem itens e não pode ser pago.",
            )

        ordem.order_status_id = self._status_cadastrado(novo_status).order_status_id
        return self.repo.salvar(ordem, commit=commit)
