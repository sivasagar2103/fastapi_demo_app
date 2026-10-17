from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from rest_api_server.services.base import ResourceService
from rest_api_server.utils import hash_password

class UserService(ResourceService):
    
    kind = "users"

    async def create_resource(self, data):
        self.authorize("create")
        data = dict(data)
        role = data["role"]
        if self.actor["role"] != "platform_admin" and role in ("platform_admin", "tenant_admin"):
            raise HTTPException(403, "Cannot grant administrator privileges at your level")
        if role == "platform_admin":
            if data["tenant_id"] or data["organization_id"]:
                raise HTTPException(422, "Platform admin must be unscoped")
        else:
            if not data["tenant_id"]:
                raise HTTPException(422, "Tenant is required")
            await self.get("tenants", data["tenant_id"])
            if role == "organization_admin" and not data["organization_id"]:
                raise HTTPException(422, "Organization admin requires an organization")
            if role == "tenant_admin" and data["organization_id"]:
                raise HTTPException(422, "Tenant admin must not be organization scoped")
            if data["organization_id"]:
                org = await self.get("organizations", data["organization_id"])
                if org["tenant_id"] != data["tenant_id"]:
                    raise HTTPException(422, "Organization must belong to tenant")
        data["password_hash"] = await run_in_threadpool(hash_password, data.pop("password"))
        data["active"] = True
        return await self.repository.create(data)

    async def update_resource(self, record_id, data):
        self.authorize("update")
        item = await self.get_resource(record_id)
        if record_id == self.actor["id"]:
            raise HTTPException(409, "Cannot deactivate your own account")
        if self.actor["role"] != "platform_admin" and item["role"] in ("platform_admin", "tenant_admin"):
            raise HTTPException(403, "Cannot change peer administrator accounts")
        return await self.repository.update(record_id, data)
