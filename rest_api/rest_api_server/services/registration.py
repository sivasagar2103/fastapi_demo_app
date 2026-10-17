
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from rest_api_server.utils import hash_password

class UserRegistrationService:
    def __init__(self, repositories, authentication):
        self.repositories = repositories
        self.authentication = authentication

    async def register(self, data):
        if await self.repositories.users.by_username(data["username"]):
            raise HTTPException(409, "Username already registered; use login")
        tenant = await self.repositories.tenants.create(
            {"name": data.get("tenant_name") or 
             f"{data['username']}'s tenant"})
        role = data.get("role", "tenant_admin")
        if role not in ("tenant_admin", "organization_admin", "viewer"):
            raise HTTPException(422, "Unsupported self-registration role")
        organization = None
        if role == "organization_admin":
            organization = await self.repositories.organizations.create({
                "name": "Default organization", "tenant_id": tenant["id"],
            })
        user = await self.repositories.users.create({
            "username": data["username"],
            "password_hash": await run_in_threadpool(hash_password, data["password"]),
            "role": role,
            "tenant_id": tenant["id"],
            "organization_id": organization["id"] if organization else None, "active": True,
        })
        return {**self.authentication.token_for(user), "user": user}
