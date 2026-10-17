
from sqlalchemy import delete, select
from rest_api_server.models import GroupMembership

class MembershipRepository:
    def __init__(self, session):
        self.session = session

    async def add(self, group_id, employee_id, organization_id):
        if not await self.session.get(GroupMembership, (group_id, employee_id)):
            self.session.add(GroupMembership(group_id = group_id,
                                             employee_id = employee_id,
                                             organization_id = organization_id))
            await self.session.flush()

    async def remove(self, group_id, employee_id):
        await self.session.execute(delete(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.employee_id == employee_id))

    async def member_ids(self, group_id):
        return list(await self.session.scalars(select(GroupMembership.employee_id).where(
            GroupMembership.group_id == group_id).order_by(GroupMembership.employee_id)))
