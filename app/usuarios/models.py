"""Entidade `usuario`: apenas a tabela, sem regra de negócio."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Usuario(Base):
    __tablename__ = "tb_usuarios"

    usuario_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Sem senha/login: o usuário guarda só nome e endereço de entrega.
    address: Mapped[str] = mapped_column(String(300), nullable=False)
