"""Regra de negócio de `usuario`. É aqui que o erro HTTP é decidido."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.usuarios.models import Usuario
from app.usuarios.repository import UsuarioRepository
from app.usuarios.schemas import Token, UsuarioCreate, UsuarioUpdate


class UsuarioService:
    def __init__(self, db: Session) -> None:
        self.repository = UsuarioRepository(db)

    def list(self, skip: int = 0, limit: int = 100) -> list[Usuario]:
        return self.repository.list(skip=skip, limit=limit)

    def get(self, usuario_id: int) -> Usuario:
        usuario = self.repository.get_by_id(usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuário {usuario_id} não encontrado.",
            )
        return usuario

    def create(self, data: UsuarioCreate) -> Usuario:
        return self.repository.save(Usuario(name=data.name, address=data.address))

    def update(self, usuario_id: int, data: UsuarioUpdate) -> Usuario:
        usuario = self.get(usuario_id)
        if data.name is not None:
            usuario.name = data.name
        if data.address is not None:
            usuario.address = data.address
        return self.repository.save(usuario)

    def delete(self, usuario_id: int) -> None:
        usuario = self.get(usuario_id)

        pedidos = self.repository.count_orders(usuario_id)
        if pedidos > 0:
            # Melhor devolver 409 legível do que deixar pedido órfão.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Usuário {usuario_id} possui {pedidos} pedido(s) "
                    "e não pode ser removido."
                ),
            )

        self.repository.delete(usuario)

    @staticmethod
    def autenticar(email: str, password: str, db: Session) -> Token:
        user = UsuarioRepository(db).get_by_email(email)
        hashed = getattr(user, "password", None) if user else None

        if not user or not hashed or not verify_password(password, hashed):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="email ou senha invalida",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(data={"sub": user.email})
        return Token(access_token=access_token)
