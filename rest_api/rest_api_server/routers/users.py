
from fastapi import APIRouter, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from rest_api_server.dependencies import user_service, user_registration_service, auth_service, current_user
from rest_api_server.schemas import UserCreate, UserOut, UserUpdate, PermissionSummary, UserRegistration, UserRegistrationResponse, UserLogin, Token

router = APIRouter(prefix = "/users", tags = ["Users"])


@router.post("/register", response_model = UserRegistrationResponse, status_code = 201)
async def register_user(payload: UserRegistration,
                        service = Depends(user_registration_service)):
    return await service.register(payload.model_dump())

@router.post("/login", response_model = Token)
async def login_user(payload: UserLogin, service = Depends(auth_service)):
    return await service.login(payload.username, payload.password)

@router.post("/token", response_model = Token)
async def generate_user_token(form: OAuth2PasswordRequestForm = Depends(),
                              service = Depends(auth_service)):
    return await service.login(form.username, form.password)

@router.get("/me", response_model = UserOut)
async def get_current_user(user=Depends(current_user)):
    return user

@router.get("", response_model = list[UserOut])
async def list_users(offset: int = Query(0, ge=0),
                     limit: int = Query(50, ge=1, le=100),
                     service = Depends(user_service)):
    return await service.list_resources(offset, limit)

@router.post("", response_model = UserOut, status_code = 201)
async def create_user(body: UserCreate, service = Depends(user_service)):
    return await service.create_resource(body.model_dump(mode = "json"))


from rest_api_server.services.authorization import AuthorizationService

@router.get("/me/permissions", response_model=PermissionSummary)
async def get_my_permissions(user=Depends(current_user)):
    return AuthorizationService(user).summary()

@router.get("/{record_id}", response_model=UserOut)
async def get_user(record_id: str, service=Depends(user_service)):
    return await service.get_resource(record_id)

@router.patch("/{record_id}", response_model=UserOut)
async def update_user(record_id: str, body: UserUpdate, service=Depends(user_service)):
    return await service.update_resource(record_id, body.model_dump())
