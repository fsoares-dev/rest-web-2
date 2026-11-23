"""Produto: DELETE apaga de verdade (não desativa)."""

from app.models.product import Product


def test_delete_apaga_o_produto_de_verdade(client, db, ids):
    resp = client.delete(f"/products/{ids['cabo']}")

    assert resp.status_code == 204
    assert client.get(f"/products/{ids['cabo']}").status_code == 404
    db.expire_all()
    assert db.get(Product, ids["cabo"]) is None  # sumiu da tabela, não só active=False


def test_delete_produto_inexistente_retorna_404(client):
    assert client.delete("/products/9999").status_code == 404


def test_delete_produto_que_esta_em_pedido_retorna_409(client, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 1})

    assert client.delete(f"/products/{ids['mouse']}").status_code == 409
    assert client.get(f"/products/{ids['mouse']}").status_code == 200


def test_produto_volta_a_ser_apagavel_depois_que_o_pedido_e_apagado(client, ids):
    client.post(f"/orders/{ids['order']}/items", json={"product_id": ids["mouse"], "quantity": 1})
    client.patch(f"/orders/{ids['order']}/cancel")
    client.delete(f"/orders/{ids['order']}")

    assert client.delete(f"/products/{ids['mouse']}").status_code == 204
