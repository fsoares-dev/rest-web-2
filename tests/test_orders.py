"""Fatia do Lucas, parte B: tb_ordem (ciclo de vida do pedido)."""

from decimal import Decimal

import pytest

from app.models.product import Product
from app.tb_ordem.models import OrderStatus, StatusNome, tb_ordem
from app.usuarios.models import Usuario


@pytest.fixture
def usuario(db) -> Usuario:
    u = Usuario(name="Lucas", address="Rua A, 1")
    db.add(u)
    db.commit()
    return u


def _estoque(db, product_id: int) -> int:
    db.expire_all()
    return db.get(Product, product_id).stock


def _definir_status(db, order_id: int, nome: StatusNome) -> None:
    linha = db.query(OrderStatus).filter_by(status_name=nome.value).one()
    db.get(tb_ordem, order_id).order_status_id = linha.order_status_id
    db.commit()


# --- criação e leitura --------------------------------------------------------


def test_criar_pedido_nasce_pendente_e_zerado(client, usuario):
    resp = client.post("/orders", json={"user_id": usuario.usuario_id})

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "Pendente"
    assert Decimal(body["total_value"]) == Decimal("0.00")
    assert body["itens"] == []


def test_criar_pedido_de_usuario_inexistente_retorna_422(client):
    resp = client.post("/orders", json={"user_id": 9999})

    assert resp.status_code == 422


def test_buscar_pedido_inexistente_retorna_404(client):
    assert client.get("/orders/9999").status_code == 404


def test_pedido_traz_itens_com_formato_do_order_item(client, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 2})

    body = client.get(f"/orders/{ids['order']}").json()

    assert Decimal(body["total_value"]) == Decimal("159.80")
    assert len(body["itens"]) == 1
    item = body["itens"][0]
    assert item["product_name"] == "Mouse"
    assert Decimal(item["price"]) == Decimal("79.90")
    assert Decimal(item["subtotal"]) == Decimal("159.80")


def test_listar_filtra_por_status(client, ids):
    resp = client.get("/orders", params={"status": "Pago"})

    assert resp.status_code == 200
    assert [o["order_id"] for o in resp.json()] == [ids["closed_order"]]


def test_listar_pedidos_do_usuario_filtra_pelo_dono(client, db, usuario):
    # O conftest já cria 2 pedidos com user_id=1, que é o id deste usuário.
    pedido = client.post("/orders", json={"user_id": usuario.usuario_id}).json()
    outro = Usuario(name="Outro", address="Rua B, 2")
    db.add(outro)
    db.commit()

    do_usuario = client.get(f"/users/{usuario.usuario_id}/orders")
    do_outro = client.get(f"/users/{outro.usuario_id}/orders")

    assert do_usuario.status_code == 200
    assert pedido["order_id"] in [o["order_id"] for o in do_usuario.json()]
    assert all(o["user_id"] == usuario.usuario_id for o in do_usuario.json())
    assert do_outro.status_code == 200
    assert do_outro.json() == []


def test_listar_pedidos_de_usuario_inexistente_retorna_404(client):
    assert client.get("/users/9999/orders").status_code == 404


# --- transições de status -----------------------------------------------------


def test_fluxo_completo_pendente_pago_enviado_entregue(client, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 1})

    for destino in ("Pago", "Enviado", "Entregue"):
        resp = client.patch(f"/orders/{ids['order']}/status", json={"status": destino})
        assert resp.status_code == 200
        assert resp.json()["status"] == destino


def test_transicao_invalida_retorna_409(client, ids):
    # Pendente -> Enviado pula o Pago.
    resp = client.patch(f"/orders/{ids['order']}/status", json={"status": "Enviado"})

    assert resp.status_code == 409


def test_status_desconhecido_retorna_422(client, ids):
    resp = client.patch(f"/orders/{ids['order']}/status", json={"status": "Inventado"})

    assert resp.status_code == 422


def test_pagar_pedido_sem_itens_retorna_422(client, ids):
    resp = client.patch(f"/orders/{ids['order']}/status", json={"status": "Pago"})

    assert resp.status_code == 422


# --- cancelamento e estoque ---------------------------------------------------


def test_cancelar_pedido_pendente_devolve_estoque(client, db, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 3})
    assert _estoque(db, ids["mouse"]) == 7

    resp = client.patch(f"/orders/{ids['order']}/cancel")

    assert resp.status_code == 200
    assert resp.json()["status"] == "Cancelado"
    assert _estoque(db, ids["mouse"]) == 10


def test_cancelar_pedido_pago_devolve_estoque_de_todos_os_itens(client, db, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 2})
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["teclado"], "quantity": 4})
    client.patch(f"/orders/{ids['order']}/status", json={"status": "Pago"})

    resp = client.patch(f"/orders/{ids['order']}/cancel")

    assert resp.status_code == 200
    assert _estoque(db, ids["mouse"]) == 10
    assert _estoque(db, ids["teclado"]) == 5


def test_cancelar_via_patch_tambem_devolve_estoque(client, db, ids):
    """O PATCH com 'Cancelado' não pode ser um caminho que pula a devolução."""
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 3})

    resp = client.patch(f"/orders/{ids['order']}/status", json={"status": "Cancelado"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "Cancelado"
    assert _estoque(db, ids["mouse"]) == 10


def test_cancelar_pedido_entregue_retorna_409_e_nao_mexe_no_estoque(client, db, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 3})
    _definir_status(db, ids["order"], StatusNome.ENTREGUE)

    resp = client.patch(f"/orders/{ids['order']}/cancel")

    assert resp.status_code == 409
    assert _estoque(db, ids["mouse"]) == 7


def test_cancelar_duas_vezes_nao_devolve_estoque_duas_vezes(client, db, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 3})
    client.patch(f"/orders/{ids['order']}/cancel")

    resp = client.patch(f"/orders/{ids['order']}/cancel")

    assert resp.status_code == 409
    assert _estoque(db, ids["mouse"]) == 10


def test_cancelar_pedido_inexistente_retorna_404(client):
    assert client.patch("/orders/9999/cancel").status_code == 404


def test_pedido_cancelado_nao_aceita_mais_itens(client, ids):
    client.patch(f"/orders/{ids['order']}/cancel")

    resp = client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 1})

    assert resp.status_code == 409


def test_cancelar_com_post_nao_existe_mais(client, ids):
    resp = client.post(f"/orders/{ids['order']}/cancel")

    assert resp.status_code == 405


def test_cancelar_e_atomico_se_a_devolucao_de_estoque_falha(client, db, ids, monkeypatch):
    """Se a devolução falhar, o pedido NÃO pode ficar cancelado nem o estoque
    meio devolvido."""
    from app.services.product import ProductService

    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 3})
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["teclado"], "quantity": 2})

    original = ProductService.increase_stock
    chamadas = []

    def falha_na_segunda(self, product_id, qty):
        chamadas.append(product_id)
        if len(chamadas) == 2:
            raise RuntimeError("falha simulada")
        return original(self, product_id, qty)

    monkeypatch.setattr(ProductService, "increase_stock", falha_na_segunda)
    with pytest.raises(RuntimeError):
        client.patch(f"/orders/{ids['order']}/cancel")
    monkeypatch.undo()

    db.expire_all()
    assert db.get(tb_ordem, ids["order"]).ordem_status.status_name == "Pendente"
    assert _estoque(db, ids["mouse"]) == 7
    assert _estoque(db, ids["teclado"]) == 3


# --- apagar pedido ------------------------------------------------------------


def test_apagar_pedido_cancelado_remove_pedido_e_itens(client, db, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 2})
    client.patch(f"/orders/{ids['order']}/cancel")

    resp = client.delete(f"/orders/{ids['order']}")

    assert resp.status_code == 204
    assert client.get(f"/orders/{ids['order']}").status_code == 404
    assert _estoque(db, ids["mouse"]) == 10  # não devolve de novo


@pytest.mark.parametrize("chave", ["order", "closed_order"])
def test_apagar_pedido_nao_cancelado_retorna_409(client, ids, chave):
    resp = client.delete(f"/orders/{ids[chave]}")

    assert resp.status_code == 409
    assert client.get(f"/orders/{ids[chave]}").status_code == 200


def test_apagar_pedido_inexistente_retorna_404(client):
    assert client.delete("/orders/9999").status_code == 404


# --- status dentro de /orders -------------------------------------------------


def test_listar_status_devolve_todos_do_enum(client):
    resp = client.get("/orders/statuses")

    assert resp.status_code == 200
    assert {s["status_name"] for s in resp.json()} == {m.value for m in StatusNome}


def test_rota_antiga_ordem_status_nao_existe_mais(client):
    assert client.get("/ordem-status").status_code == 404


def test_filtro_por_status_invalido_retorna_422(client):
    assert client.get("/orders", params={"status": "Inventado"}).status_code == 422


# --- paginação ----------------------------------------------------------------


def test_listar_pedidos_aceita_skip_e_limit(client, ids):
    todos = [o["order_id"] for o in client.get("/orders").json()]

    pagina = client.get("/orders", params={"skip": 1, "limit": 1}).json()

    assert len(todos) == 2
    assert [o["order_id"] for o in pagina] == todos[1:2]
    assert client.get("/orders", params={"limit": 0}).status_code == 422


# --- fechar pedido ------------------------------------------------------------


def test_fechar_pedido_com_item_vira_pago(client, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 1})

    resp = client.post(f"/orders/{ids['order']}/close")

    assert resp.status_code == 200
    assert resp.json()["status"] == "Pago"
    assert Decimal(resp.json()["total_value"]) == Decimal("79.90")


def test_fechar_pedido_sem_itens_retorna_422(client, ids):
    assert client.post(f"/orders/{ids['order']}/close").status_code == 422
