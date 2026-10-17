"""Read-only aggregate queries; no credentials or personal contact data leave SQL."""
from sqlalchemy import func, select
from rest_api_server.models import Organization, Employee, EmployeeGroup, User, GroupMembership

class TenantReportRepository:
    def __init__(self, session):
        self.session = session

    async def snapshot(self, tenant, actor):
        tenant_id = tenant['id']
        organization_id = actor['organization_id'] if actor['role'] != 'platform_admin' else None
        def scope(model):
            clauses = [model.tenant_id == tenant_id]
            if organization_id:
                clauses.append((model.id if model is Organization else model.organization_id) == organization_id)
            return clauses
        async def count(model, *extra):
            return await self.session.scalar(select(func.count()).select_from(model).where(*scope(model), *extra))
        counts = {name: await count(model) for name, model in [('organizations',Organization), ('employees',Employee), ('employee_groups',EmployeeGroup), ('users',User)]}
        counts['active_users'] = await count(User, User.active.is_(True))
        roles = (await self.session.execute(select(User.role, func.count()).where(*scope(User)).group_by(User.role))).all()
        jobs = (await self.session.execute(select(Employee.job_title, func.count()).where(*scope(Employee)).group_by(Employee.job_title).order_by(func.count().desc()).limit(20))).all()
        organizations = (await self.session.execute(select(Organization.id, Organization.name).where(*scope(Organization)).order_by(Organization.id).limit(50))).all()
        groups = (await self.session.execute(select(EmployeeGroup.name, func.count(GroupMembership.employee_id)).outerjoin(GroupMembership, GroupMembership.group_id == EmployeeGroup.id).where(*scope(EmployeeGroup)).group_by(EmployeeGroup.id, EmployeeGroup.name).order_by(EmployeeGroup.id).limit(50))).all()
        return {'tenant': {'id':tenant_id,'name':tenant['name']},
                'visibility': {'scope':'organization' if organization_id else 'tenant', 'organization_id':organization_id},
                'counts': counts, 'user_roles': dict(roles),
                'job_titles': [{'title': title or 'Unspecified', 'count': number} for title, number in jobs],
                'organizations': [{'id':row.id,'name':row.name} for row in organizations],
                'groups': [{'name':name,'member_count':number} for name,number in groups],
                'limits': {'organization_rows':50,'group_rows':50,'job_title_rows':20},
                'note':'Counts cover all authorized rows. Detail lists are limited. Organization-scoped reports are not full-tenant reports.'}
