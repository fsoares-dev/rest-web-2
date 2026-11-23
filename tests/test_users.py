"""Usuário: só nome e endereço, sem senha."""

from app.main import app
from app.usuarios.dependencies import get_current_user
from app.usuarios.models import Usuario


def test_criar_usuario_devolve_nome_e_endereco_sem_senha(client):
    resp = client.post("/users", json={"name": "Ana", "address": "Rua X, 10"})

    assert resp.status_code == 201
    assert set(resp.json()) == {"usuario_id", "name", "address"}


def test_criar_usuario_sem_endereco_retorna_422(client):
    assert client.post("/users", json={"name": "Ana"}).status_code == 422


def test_criar_usuario_com_senha_ignora_o_campo(client):
    resp = client.post("/users", json={"name": "Ana", "address": "Rua X", "password": "123"})

    assert resp.status_code == 201
    assert "password" not in resp.json()


def test_atualizar_endereco_parcialmente(client):
    uid = client.post("/users", json={"name": "Ana", "address": "Rua X"}).json()["usuario_id"]

    resp = client.patch(f"/users/{uid}", json={"address": "Rua Y"})

    assert resp.status_code == 200
    assert resp.json()["address"] == "Rua Y"
    assert resp.json()["name"] == "Ana"


def test_rota_de_senha_nao_existe(client):
    assert client.patch("/users/1/password", json={"password": "x"}).status_code == 404


def test_apagar_usuario_sem_pedidos(client):
    # O conftest já cria 2 pedidos com user_id=1, então o 1º usuário tem pedidos;
    # apagamos o 2º, que não tem nenhum.
    client.post("/users", json={"name": "Dono dos pedidos do conftest", "address": "Rua Z"})
    uid = client.post("/users", json={"name": "Ana", "address": "Rua X"}).json()["usuario_id"]

    app.dependency_overrides[get_current_user] = lambda: Usuario(
        usuario_id=uid, name="Ana", address="Rua X"
    )
    assert client.delete(f"/users/{uid}").status_code == 204
    assert client.get(f"/users/{uid}").status_code == 404


def test_apagar_usuario_com_pedidos_retorna_409(client):
    uid = client.post("/users", json={"name": "Ana", "address": "Rua X"}).json()["usuario_id"]
    client.post("/orders", json={"user_id": uid})

    assert client.delete(f"/users/{uid}").status_code == 409


def test_ler_usuario_logado_me(client):
    resp = client.get("/users/me")

    assert resp.status_code == 200
    assert resp.json()["usuario_id"] == 1
    assert resp.json()["name"] == "Usuário Teste"


def test_rotas_protegidas_sem_token_retornam_401(client):
    app.dependency_overrides.pop(get_current_user, None)

    assert client.get("/users/me").status_code == 401
    assert client.patch("/users/1", json={"address": "Rua Y"}).status_code == 401
    assert client.delete("/users/1").status_code == 401
    assert client.post("/orders", json={"user_id": 1}).status_code == 401
    assert client.post("/products", json={"name": "X", "price": 10, "stock": 1, "category_id": 1}).status_code == 401
    assert client.post("/categories", json={"name": "Nova"}).status_code == 401


def test_cadastro_usuario_nao_exige_autenticacao(client):
    app.dependency_overrides.pop(get_current_user, None)

    resp = client.post("/users", json={"name": "Sem Token", "address": "Rua Aberta, 1"})
    assert resp.status_code == 201


def test_alterar_ou_apagar_outro_usuario_retorna_403(client):
    client.post("/users", json={"name": "Usuario 1", "address": "Rua 1"})
    outro_id = client.post("/users", json={"name": "Usuario 2", "address": "Rua 2"}).json()["usuario_id"]

    # current_user no conftest tem usuario_id=1, tentando alterar/apagar usuario_id=2
    assert client.patch(f"/users/{outro_id}", json={"address": "Hack"}).status_code == 403
    assert client.delete(f"/users/{outro_id}").status_code == 403
