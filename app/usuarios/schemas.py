"""DTOs Pydantic de `usuario` (entrada e saída)."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UsuarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=300)


class UsuarioUpdate(BaseModel):
    """Atualização parcial: só o que vier no corpo é alterado."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=300)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usuario_id: int
    name: str
    address: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None
    