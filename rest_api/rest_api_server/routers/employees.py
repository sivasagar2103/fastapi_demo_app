
from fastapi import APIRouter, Depends, Query, Response
from rest_api_server.dependencies import employee_service
from rest_api_server.schemas import EmployeeCreate, EmployeeOut, EmployeeUpdate

router = APIRouter(prefix = "/employees", tags = ["Employees"])


@router.get("", response_model = list[EmployeeOut])
async def list_employees(offset: int = Query(0, ge = 0),
                         limit: int = Query(50, ge = 1, le = 100),
                         service = Depends(employee_service)):
    return await service.list_resources(offset, limit)

@router.post("", response_model = EmployeeOut, status_code = 201)
async def create_employee(body: EmployeeCreate, service = Depends(employee_service)):
    return await service.create_resource(body.model_dump(mode = "json"))

@router.get("/{record_id}", response_model = EmployeeOut)
async def get_employee(record_id: str, service = Depends(employee_service)):
    return await service.get_resource(record_id)

@router.patch("/{record_id}", response_model = EmployeeOut)
async def update_employee(record_id: str, body: EmployeeUpdate,
                          service = Depends(employee_service)):
    return await service.update_resource(record_id, body.model_dump(mode = "json"))

@router.delete("/{record_id}", status_code = 204)
async def delete_employee(record_id: str, service = Depends(employee_service)):
    await service.delete_resource(record_id)
    return Response(status_code = 204)
