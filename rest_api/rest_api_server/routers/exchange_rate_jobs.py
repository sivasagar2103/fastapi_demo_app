from fastapi import APIRouter, Depends, Query, Response
from rest_api_server.dependencies import repositories, current_user
from rest_api_server.services.exchange_rate_jobs import ExchangeRateJobService
from rest_api_server.schemas import ExchangeRateJobCreate, ExchangeRateJobOut

router = APIRouter(prefix='/tenants/{tenant_id}/exchange-rate-jobs', tags=['Worker jobs'])

def service(repos=Depends(repositories), actor=Depends(current_user)):
    return ExchangeRateJobService(repos, actor)

@router.post('', response_model=ExchangeRateJobOut, status_code=202)
async def create_job(tenant_id: str, payload: ExchangeRateJobCreate, response: Response, svc=Depends(service)):
    job = await svc.submit(tenant_id,payload.model_dump())
    response.headers['Location'] = f"/api/v1/tenants/{tenant_id}/exchange-rate-jobs/{job['id']}"
    return job

@router.get('', response_model=list[ExchangeRateJobOut])
async def list_jobs(tenant_id: str, offset: int=Query(0,ge=0), limit: int=Query(50,ge=1,le=100),svc=Depends(service)):
    return await svc.list_jobs(tenant_id,offset,limit)

@router.get('/{job_id}', response_model=ExchangeRateJobOut)
async def get_job(tenant_id: str,job_id: str,svc=Depends(service)):
    return await svc.get_job(tenant_id,job_id)
