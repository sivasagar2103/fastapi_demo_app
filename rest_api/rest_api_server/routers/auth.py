
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from rest_api_server.dependencies import auth_service, current_user
from rest_api_server.schemas import Token, UserOut

router = APIRouter(prefix = "/auth", tags = ["Authentication"])

@router.post("/token", response_model = Token)
async def login(form: OAuth2PasswordRequestForm = Depends(),
                service = Depends(auth_service)):
    return await service.login(form.username, form.password)

@router.get("/me", response_model = UserOut)
async def me(user = Depends(current_user)):
    return user
