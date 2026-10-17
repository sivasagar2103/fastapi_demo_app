"""Wire request-scoped sessions, repositories and application services."""
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from rest_api_server.globals import get_session
from rest_api_server.repositories import Repositories
from rest_api_server.services.auth import AuthService
from rest_api_server.services.registration import UserRegistrationService
from rest_api_server.services.tenants import TenantService
from rest_api_server.services.organizations import OrganizationService
from rest_api_server.services.users import UserService
from rest_api_server.services.employees import EmployeeService
from rest_api_server.services.employee_groups import EmployeeGroupService

oauth2 = OAuth2PasswordBearer(tokenUrl = "/api/v1/users/token")

def repositories(session: AsyncSession = Depends(get_session, scope="function")):
    return Repositories(session)

def auth_service(request: Request, repos = Depends(repositories)):
    return AuthService(repos, request.app.state.settings)

async def current_user(token: str = Depends(oauth2),
                       service = Depends(auth_service)):
    return await service.authenticate(token)

def tenant_service(repos=Depends(repositories), actor=Depends(current_user)):
    return TenantService(repos, actor)

def organization_service(repos=Depends(repositories), actor=Depends(current_user)):
    return OrganizationService(repos, actor)

def user_service(repos=Depends(repositories), actor=Depends(current_user)):
    return UserService(repos, actor)

def employee_service(repos=Depends(repositories), actor=Depends(current_user)):
    return EmployeeService(repos, actor)

def employee_group_service(repos=Depends(repositories), actor=Depends(current_user)):
    return EmployeeGroupService(repos, actor)

def user_registration_service(repos=Depends(repositories), authentication=Depends(auth_service)):
    return UserRegistrationService(repos, authentication)


from rest_api_server.services.tenant_summaries import TenantSummaryService, FoundrySummaryProvider

def summary_provider(request: Request):
    return FoundrySummaryProvider(request.app.state.settings)

def tenant_summary_service(tenants=Depends(tenant_service), session: AsyncSession=Depends(get_session, scope="function"), provider=Depends(summary_provider)):
    return TenantSummaryService(tenants, session, provider)
