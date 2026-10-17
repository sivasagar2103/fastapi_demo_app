from fastapi import HTTPException
from rest_api_server.services.base import ResourceService

class ExchangeRateJobService(ResourceService):
    kind = "exchange-rate-jobs"

    async def submit(self, tenant_id, data):
        self.authorize('create')
        await self.get('tenants', tenant_id)
        organization_id = data.get('organization_id') or self.actor['organization_id']
        if organization_id:
            organization = await self.get('organizations', organization_id)
            if organization['tenant_id'] != tenant_id:
                raise HTTPException(422, 'Organization must belong to tenant')
        return await self.repository.create({'tenant_id':tenant_id, 'organization_id':organization_id,
            'created_by':self.actor['id'], 'base_currency':data['base_currency']})

    async def list_jobs(self, tenant_id, offset, limit):
        self.authorize('read')
        await self.get('tenants',tenant_id)
        # Apply tenant selection before pagination, also for platform admins.
        actor = {**self.actor, 'role':'viewer', 'tenant_id':tenant_id}
        return await self.repository.list(actor, offset, limit, newest_first=True)

    async def get_job(self, tenant_id, job_id):
        await self.get('tenants',tenant_id)
        job = await self.get_resource(job_id)
        if job['tenant_id'] != tenant_id:
            raise HTTPException(404,'Resource not found')
        return job
