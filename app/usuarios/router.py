"""Controller de usuário — só traduz HTTP."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.usuarios.dependencies import get_current_user
from app.usuarios.models import Usuario
from app.usuarios.schemas import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.usuarios.services import UsuarioService

router = APIRouter(prefix="/users", tags=["Usuários"])


def get_service(db: Annotated[Session, Depends(get_db)]) -> UsuarioService:
    return UsuarioService(db)

Service = Annotated[UsuarioService, Depends(get_service)]

@router.get("", response_model=list[UsuarioOut], status_code=status.HTTP_200_OK,)
def listar_usuarios(
    service: Service,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
):
    return service.list(skip=skip, limit=limit)


@router.get("/me", response_model=UsuarioOut)
def ler_usuario_logado(current_user: Usuario = Depends(get_current_user)):
    return current_user


@router.get(
    "/{usuario_id}", response_model=UsuarioOut, status_code=status.HTTP_200_OK
)
def buscar_usuario(usuario_id: int, service: Service):
    return service.get(usuario_id)


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: UsuarioCreate, service: Service):
    return service.create(dados)


@router.patch(
    "/{usuario_id}", response_model=UsuarioOut, status_code=status.HTTP_200_OK
)
def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdate,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
):
    if current_user.usuario_id != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para alterar outro usuário.",
        )
    return service.update(usuario_id, dados)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_usuario(
    usuario_id: int,
    service: Service,
    current_user: Usuario = Depends(get_current_user),
) -> None:
    if current_user.usuario_id != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para alterar outro usuário.",
        )
    service.delete(usuario_id)
