
from fastapi import HTTPException
from rest_api_server.services.base import OrganizationResourceService

class EmployeeGroupService(OrganizationResourceService):
    kind = "employee-groups"

    async def members(self, group_id):
        await self.get_resource(group_id)
        ids = await self.repositories.memberships.member_ids(group_id)
        return [await self.get("employees", employee_id) for employee_id in ids]

    async def member(self, group_id, employee_id, add):
        self.authorize("manage_members")
        group = await self.get_resource(group_id)
        employee = await self.get("employees", employee_id)
        if group["organization_id"] != employee["organization_id"]:
            raise HTTPException(422, "Group and employee must belong to the same organization")
        if add:
            await self.repositories.memberships.add(group_id, employee_id, group["organization_id"])
        else:
            await self.repositories.memberships.remove(group_id, employee_id)
