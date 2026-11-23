# E-commerce API

API em FastAPI com **arquitetura em camadas** (equivalente ao padrão do Spring Boot).

## Estrutura

```
app/
├── core/
│   └── security.py         # JWT (python-jose), hash bcrypt (passlib) e leitura de env
├── database.py             # engine, SessionLocal, Base, get_db
├── main.py                 # app, registro de routers, /health, create_all
├── models/                 # entidades de categoria e produto (tabelas)
│   └── __init__.py         # importa TODOS os models (create_all enxerga)
├── tb_ordem/               # pedidos + status do pedido (models/schemas/repository/services/router)
├── order_item/             # itens do pedido
└── usuarios/               # usuários, login (/auth/login) e dependência JWT (get_current_user)
├── schemas/  repositories/  services/  routers/   # camadas de categoria e produto
```

Fluxo da requisição: `router` → `service` → `repository` → banco.

| Camada | Responsabilidade |
| --- | --- |
| `model` | tabela SQLAlchemy, sem lógica |
| `repository` | só query/insert/update/delete |
| `service` | regra de negócio e decisão de erro (`HTTPException`) |
| `schema` | Pydantic `Create` / `Update` / `Out` |
| `router` | recebe request, injeta `get_db`, chama o service |

## De/Para com Spring Boot

| Spring Boot | FastAPI |
| --- | --- |
| `@RestController` | `APIRouter` |
| DTO | Schema Pydantic |
| `@Service` | `services/` |
| `@Repository` | `repositories/` |
| Entidade JPA/Hibernate | Model SQLAlchemy |

## Convenção de erros

| Status | Quando |
| --- | --- |
| `200` | leitura / atualização |
| `201` | criação |
| `204` | remoção |
| `401` | não autenticado (token JWT ausente, inválido ou expirado; ou credenciais inválidas no login) |
| `403` | proibido (regra anti-IDOR: tentativa de alterar ou apagar outro usuário) |
| `404` | recurso não encontrado |
| `405` | método não permitido (ex.: `POST /orders/{id}/cancel` — agora é `PATCH`) |
| `409` | conflito (nome duplicado, categoria com produtos, produto/usuário com pedidos, estoque insuficiente, transição de status inválida, apagar pedido não cancelado) |
| `422` | referência/valor inválido (categoria ou usuário inexistente, pagar sem itens, status desconhecido) |

## Endpoints

Listagens aceitam paginação: `skip` (quantos registros pular, o *offset*) e
`limit` (máximo por página, 1–200, padrão 100). Rotas marcadas com **JWT**
exigem o header `Authorization: Bearer <token>`.

| Método | Rota | Auth | Status |
| --- | --- | --- | --- |
| GET | `/health` | Pública | `200` |
| POST | `/auth/login` | Pública | `200` · `401` — formulário OAuth2 (`username` + `password`) |
| GET | `/categories` | Pública | `200` |
| GET | `/categories/{id}` | Pública | `200` · `404` |
| POST | `/categories` | JWT | `201` · `401` · `409` |
| PATCH | `/categories/{id}` | JWT | `200` · `401` · `404` · `409` |
| DELETE | `/categories/{id}` | JWT | `204` · `401` · `404` · `409` (tem produtos vinculados) |
| GET | `/products` | Pública | `200` — só ativos por padrão (`?active=null` para todos) |
| GET | `/products/{id}` | Pública | `200` · `404` |
| POST | `/products` | JWT | `201` · `401` · `409` · `422` |
| PATCH | `/products/{id}` | JWT | `200` · `401` · `404` · `409` · `422` |
| DELETE | `/products/{id}` | JWT | `204` · `401` · `404` · `409` — **apaga de verdade**; 409 se já está em algum item de pedido |
| GET | `/users` | Pública | `200` |
| GET | `/users/me` | JWT | `200` · `401` — perfil do usuário autenticado |
| GET | `/users/{id}` | Pública | `200` · `404` |
| POST | `/users` | Pública | `201` — cadastro aberto; corpo: `name`, `address` |
| PATCH | `/users/{id}` | JWT | `200` · `401` · `403` (outro usuário) · `404` |
| DELETE | `/users/{id}` | JWT | `204` · `401` · `403` (outro usuário) · `404` · `409` (tem pedidos) |
| GET | `/users/{id}/orders` | JWT | `200` · `401` · `404` (usuário não existe) |
| GET | `/orders/statuses` | Pública | `200` — status possíveis (somente leitura) |
| GET | `/orders` | JWT | `200` · `401` — filtro opcional `?status=Pago` (valor inválido → `422`) |
| GET | `/orders/{id}` | JWT | `200` · `401` · `404` — já traz os itens |
| POST | `/orders` | JWT | `201` · `401` · `422` (usuário não existe) — nasce `Pendente` e vazio |
| PATCH | `/orders/{id}/status` | JWT | `200` · `401` · `404` · `409` · `422` |
| PATCH | `/orders/{id}/cancel` | JWT | `200` · `401` · `404` · `409` — devolve o estoque dos itens |
| POST | `/orders/{id}/close` | JWT | `200` · `401` · `404` · `409` · `422` — atalho para `Pago` |
| DELETE | `/orders/{id}` | JWT | `204` · `401` · `404` · `409` — **só pedidos `Cancelado`** (apaga os itens junto) |
| GET | `/orders/{id}/items` | JWT | `200` · `401` · `404` |
| POST | `/orders/{id}/items` | JWT | `201` · `401` · `404` · `409` · `422` |
| PATCH | `/orders/{id}/items/{product_id}` | JWT | `200` · `401` · `404` · `409` |
| DELETE | `/orders/{id}/items/{product_id}` | JWT | `204` · `401` · `404` · `409` |

## Segurança e Autenticação

A API usa autenticação **OAuth2 com Bearer JWT** (`python-jose` + `passlib` com `bcrypt`).

### Como funciona o fluxo

1. **Criptografia e geração do token** (`app/core/security.py`):
   - `get_password_hash` / `verify_password` geram e validam hashes `bcrypt`.
   - `create_access_token` assina o JWT com `SECRET_KEY`, algoritmo `ALGORITHM` (padrão `HS256`) e expiração `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão `60` minutos), gravando o identificador no claim `sub`.
   - Essas configurações podem ser sobrescritas via variáveis de ambiente no `.env`.
2. **Login** (`app/usuarios/auth_router.py` → `POST /auth/login`):
   - Recebe `OAuth2PasswordRequestForm` (`username` e `password`), delega para `UsuarioService.autenticar` e devolve `{"access_token": "...", "token_type": "bearer"}` (ou `401` se inválido).
3. **Proteção de rotas** (`app/usuarios/dependencies.py` → `get_current_user`):
   - Extrai o token do header `Authorization: Bearer <token>` via `OAuth2PasswordBearer(tokenUrl="auth/login")`.
   - Decodifica o JWT, valida o claim `sub` e busca o usuário no banco (`UsuarioRepository.get_by_email`). Qualquer falha responde `401 Unauthorized`.
   - Para proteger uma rota, injeta-se `current_user: Usuario = Depends(get_current_user)` nos parâmetros do endpoint.
4. **Rota `/users/me` e regra anti-IDOR** (`app/usuarios/router.py`):
   - `GET /users/me` está declarada **antes** de `GET /users/{usuario_id}` para evitar conflito de rota e devolve o próprio `current_user`.
   - `POST /users` permanece pública para permitir a criação da primeira conta.
   - Em `PATCH /users/{usuario_id}` e `DELETE /users/{usuario_id}`, além do JWT, o controller verifica `current_user.usuario_id != usuario_id` e responde `403 Forbidden` se um usuário tentar alterar ou apagar outra conta.

### Segurança nos testes

Em [`tests/conftest.py`](tests/conftest.py), a fixture `client` registra `app.dependency_overrides[get_current_user]` retornando um usuário simulado (`usuario_id=1`), permitindo que as suítes de produtos, pedidos e itens chamem as rotas protegidas normalmente. Os cenários específicos de autenticação (`401` sem token, `403` anti-IDOR, `/users/me` e cadastro público) ajustam ou removem esse override em [`tests/test_users.py`](tests/test_users.py).

## Contrato de estoque

A coluna `stock` é alterada **exclusivamente** pelo `ProductService`:

```python
ProductService(db).decrease_stock(product_id, qty)  # 409 se qty > stock
ProductService(db).increase_stock(product_id, qty)  # devolve ao cancelar
```

Esses métodos **não dão commit**: só fazem `flush`. Quem chama (itens de pedido,
cancelamento) confirma a transação uma única vez no fim — se qualquer passo
falhar, tudo sofre `rollback` (tudo ou nada).

## Ciclo de vida do pedido

```
Pendente ──► Pago ──► Enviado ──► Entregue
    │          │
    └──────────┴────► Cancelado
```

- Qualquer outra transição responde `409`.
- Pagar (`PATCH .../status` ou `POST .../close`) exige pelo menos um item (`422`).
- **Cancelar sempre devolve o estoque**, inclusive via `PATCH .../status` com
  `"Cancelado"`. Devolução + mudança de status acontecem na mesma transação.
- Só pedido `Cancelado` pode ser apagado (`DELETE /orders/{id}`); o estoque não é
  devolvido de novo, pois já voltou no cancelamento.

## Testes

```bash
pip install pytest httpx
pytest
```

## Como rodar

```bash
pip install -r requirements.txt        # ou: uv sync
uvicorn app.main:app --reload          # http://127.0.0.1:8000/docs
```

Configuração por `.env`: copie `.env.example` para `.env` e ajuste `DATABASE_URL`
(default `sqlite:///./ecommerce.db`). Para popular dados de teste: `python -m app.seed`.

Atenção: o `Base.metadata.create_all` não altera tabelas já existentes. Se você já
tinha um `ecommerce.db` de antes (a tabela de usuários ganhou a coluna `address`),
apague o arquivo e rode o seed de novo.

Banco via `DATABASE_URL`. As tabelas são criadas
no startup com `Base.metadata.create_all` — sem Alembic por enquanto.
