
import jwt
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from rest_api_server.utils import DUMMY_HASH, issue_token, verify_password

class AuthService:
    def __init__(self, repositories, settings):
        self.repositories = repositories
        self.users, self.settings = repositories.users, settings

    async def login(self, username, password):
        user = await self.users.by_username(username)
        valid = await run_in_threadpool(verify_password, password, 
                                        user["password_hash"] if user else DUMMY_HASH)
        if not user or not valid or not user["active"]:
            raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
        return self.token_for(user)

    def token_for(self, user):
        return {"access_token": issue_token(user, self.settings), "token_type": "bearer", "expires_in": self.settings.token_minutes * 60}

    async def authenticate(self, token):
        unauthorized = HTTPException(401, "Invalid or expired bearer token", headers={"WWW-Authenticate": "Bearer"})
        try:
            payload = jwt.decode(token, self.settings.jwt_secret, algorithms = ["HS256"],
                                 audience = "management-api", issuer = "fastapi-demo",
                                 options = {"require": ["sub", "iat", "exp", "iss", "aud"]})
            user = await self.users.get(payload["sub"])
        except (jwt.InvalidTokenError, KeyError):
            raise unauthorized from None
        if not user or not user["active"]:
            raise unauthorized
        # Resolve current role and scope from the database, never from JWT claims.
        if payload.get("tenant_id", user["tenant_id"]) != user["tenant_id"]:
            raise unauthorized
        return user
