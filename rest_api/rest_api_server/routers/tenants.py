
from fastapi import APIRouter, Depends, Query, Response
from rest_api_server.dependencies import tenant_service
from rest_api_server.schemas import TenantCreate, TenantOut, Rename

router = APIRouter(prefix = "/tenants", tags = ["Tenants"])


@router.get("", response_model = list[TenantOut])
async def list_tenants(offset: int = Query(0, ge = 0),
                       limit: int = Query(50, ge = 1, le = 100),
                       service = Depends(tenant_service)):
    return await service.list_resources(offset, limit)

@router.post("", response_model=TenantOut, status_code = 201)
async def create_tenant(body: TenantCreate, service = Depends(tenant_service)):
    return await service.create_resource(body.model_dump(mode = "json"))

@router.get("/{record_id}", response_model = TenantOut)
async def get_tenant(record_id: str, service = Depends(tenant_service)):
    return await service.get_resource(record_id)

@router.patch("/{record_id}", response_model = TenantOut)
async def update_tenant(record_id: str, body: Rename, service = Depends(tenant_service)):
    return await service.update_resource(record_id, body.model_dump(mode = "json"))

@router.delete("/{record_id}", status_code = 204)
async def delete_tenant(record_id: str, service = Depends(tenant_service)):
    await service.delete_resource(record_id)
    return Response(status_code = 204)


from fastapi.responses import StreamingResponse
from rest_api_server.dependencies import tenant_summary_service

@router.post("/{record_id}/summary/stream", response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}}, "description": "SSE events: snapshot, delta, error, done"}})
async def stream_tenant_summary(record_id: str, service=Depends(tenant_summary_service)):
    snapshot = await service.prepare(record_id)
    return StreamingResponse(service.events(snapshot), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache, no-store", "X-Accel-Buffering":"no"})


from rest_api_server.schemas import TenantChatRequest

@router.post("/{record_id}/chat/stream", response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}}, "description": "Scoped tenant chat: snapshot, delta, error, done events"}})
async def stream_tenant_chat(record_id: str, payload: TenantChatRequest, service=Depends(tenant_summary_service)):
    snapshot = await service.prepare(record_id)
    return StreamingResponse(service.events(snapshot, payload.model_dump()), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache, no-store", "X-Accel-Buffering":"no"})
