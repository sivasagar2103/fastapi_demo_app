from rest_api_server.services.base import ResourceService

class OrganizationService(ResourceService):
    kind = "organizations"

    async def create_resource(self, data):
        self.authorize("create")
        await self.get("tenants", data["tenant_id"])
        return await self.repository.create(data)
