
from fastapi import APIRouter, Depends, Query, Response
from rest_api_server.dependencies import employee_group_service
from rest_api_server.schemas import EmployeeOut, GroupCreate, GroupOut, Rename

router = APIRouter(prefix = "/employee-groups", tags = ["Employee-Groups"])


@router.get("", response_model = list[GroupOut])
async def list_employee_groups(offset: int = Query(0, ge=0),
                               limit: int = Query(50, ge=1, le=100),
                               service = Depends(employee_group_service)):
    return await service.list_resources(offset, limit)

@router.post("", response_model = GroupOut, status_code = 201)
async def create_employee_group(body: GroupCreate, service = Depends(employee_group_service)):
    return await service.create_resource(body.model_dump(mode = "json"))

@router.get("/{record_id}", response_model = GroupOut)
async def get_employee_group(record_id: str, service = Depends(employee_group_service)):
    return await service.get_resource(record_id)

@router.patch("/{record_id}", response_model = GroupOut)
async def update_employee_group(record_id: str, body: Rename,
                                service = Depends(employee_group_service)):
    return await service.update_resource(record_id, body.model_dump(mode = "json"))

@router.delete("/{record_id}", status_code = 204)
async def delete_employee_group(record_id: str, service = Depends(employee_group_service)):
    await service.delete_resource(record_id)
    return Response(status_code=204)


@router.get("/{record_id}/members", response_model = list[EmployeeOut])
async def members(record_id: str, service = Depends(employee_group_service)):
    return await service.members(record_id)

@router.put("/{record_id}/members/{employee_id}", status_code = 204)
async def add_member(record_id: str, employee_id: str,
                     service = Depends(employee_group_service)):
    await service.member(record_id, employee_id, True)
    return Response(status_code = 204)

@router.delete("/{record_id}/members/{employee_id}", status_code = 204)
async def remove_member(record_id: str, employee_id: str,
                        service = Depends(employee_group_service)):
    await service.member(record_id, employee_id, False)
    return Response(status_code = 204)
