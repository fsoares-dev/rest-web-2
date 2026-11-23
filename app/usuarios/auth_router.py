from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.usuarios import schemas
from app.usuarios.services import UsuarioService

auth_router = APIRouter(prefix="/auth", tags=["Autenticação"])

@auth_router.post("/login", response_model=schemas.Token, status_code=status.HTTP_200_OK)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    return UsuarioService.autenticar(
        email=form_data.username,
        password=form_data.password,
        db=db
    )
    