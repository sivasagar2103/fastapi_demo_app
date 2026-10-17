
from fastapi import APIRouter, Depends, Query, Response
from rest_api_server.dependencies import organization_service
from rest_api_server.schemas import OrganizationCreate, OrganizationOut, Rename

router = APIRouter(prefix = "/organizations", tags = ["Organizations"])


@router.get("", response_model = list[OrganizationOut])
async def list_organizations(offset: int = Query(0, ge = 0),
                             limit: int = Query(50, ge = 1, le = 100),
                             service = Depends(organization_service)):
    return await service.list_resources(offset, limit)

@router.post("", response_model=OrganizationOut, status_code = 201)
async def create_organization(body: OrganizationCreate,
                              service = Depends(organization_service)):
    return await service.create_resource(body.model_dump(mode = "json"))

@router.get("/{record_id}", response_model = OrganizationOut)
async def get_organization(record_id: str, service = Depends(organization_service)):
    return await service.get_resource(record_id)

@router.patch("/{record_id}", response_model = OrganizationOut)
async def update_organization(record_id: str, body: Rename,
                              service = Depends(organization_service)):
    return await service.update_resource(record_id, body.model_dump(mode = "json"))

@router.delete("/{record_id}", status_code = 204)
async def delete_organization(record_id: str, service = Depends(organization_service)):
    await service.delete_resource(record_id)
    return Response(status_code = 204)
