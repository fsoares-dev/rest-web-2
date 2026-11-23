"""Acesso a dados de `usuario`. Sem regra de negócio, sem HTTP."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.tb_ordem.models import tb_ordem
from app.usuarios.models import Usuario


class UsuarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, skip: int = 0, limit: int = 100) -> list[Usuario]:
        stmt = select(Usuario).order_by(Usuario.usuario_id).offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_by_id(self, usuario_id: int) -> Usuario | None:
        return self.db.get(Usuario, usuario_id)

    def get_by_email(self, email: str) -> Usuario | None:
        email_col = getattr(Usuario, "email", None)
        if email_col is None:
            return None
        stmt = select(Usuario).where(email_col == email)
        return self.db.scalar(stmt)

    def count_orders(self, usuario_id: int) -> int:
        """Usado pelo service antes de apagar um usuário."""
        stmt = (
            select(func.count())
            .select_from(tb_ordem)
            .where(tb_ordem.user_id == usuario_id)
        )
        return self.db.scalar(stmt) or 0

    def save(self, usuario: Usuario) -> Usuario:
        """Serve para inserir e para atualizar (a sessão sabe a diferença)."""
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def delete(self, usuario: Usuario) -> None:
        self.db.delete(usuario)
        self.db.commit()
