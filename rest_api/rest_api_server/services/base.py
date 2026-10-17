"""Shared scope policy and resource operations; domain rules live in subclasses."""
from fastapi import HTTPException
from rest_api_server.services.authorization import AuthorizationService

class ResourceService:
    
    kind: str

    def __init__(self, repositories, actor):
        self.repositories = repositories
        self.actor = actor
        self.authorization = AuthorizationService(actor)
        self.repository = repositories.resource(self.kind)

    def visible(self, kind, item):
        return self.authorization.visible(kind, item)

    async def get(self, kind, record_id):
        self.authorization.require(kind, "read")
        item = await self.repositories.resource(kind).get(record_id)
        if item is None:
            raise HTTPException(404, "Resource not found")
        if not self.visible(kind, item):
            raise HTTPException(404, "Resource not found")
        return item


    def authorize(self, action):
        self.authorization.require(self.kind, action)

    async def list_resources(self, offset, limit):
        self.authorize("read")
        return await self.repository.list(self.actor, offset, limit)

    async def get_resource(self, record_id):
        return await self.get(self.kind, record_id)

    async def create_resource(self, data):
        self.authorize("create")
        return await self.repository.create(data)

    async def update_resource(self, record_id, data):
        self.authorize("update")
        await self.get_resource(record_id)
        return await self.repository.update(record_id, data)

    async def delete_resource(self, record_id):
        self.authorize("delete")
        await self.get_resource(record_id)
        # RESTRICT foreign keys enforce dependent-resource deletion atomically.
        await self.repository.delete(record_id)

class OrganizationResourceService(ResourceService):

    async def create_resource(self, data):
        self.authorize("create")
        organization = await self.get("organizations", data["organization_id"])
        return await self.repository.create({**data, "tenant_id": organization["tenant_id"]})
