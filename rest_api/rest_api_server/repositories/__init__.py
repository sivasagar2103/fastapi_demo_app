
from rest_api_server.repositories.tenants import TenantRepository
from rest_api_server.repositories.organizations import OrganizationRepository
from rest_api_server.repositories.users import UserRepository
from rest_api_server.repositories.employees import EmployeeRepository
from rest_api_server.repositories.employee_groups import EmployeeGroupRepository
from rest_api_server.repositories.memberships import MembershipRepository



from rest_api_server.repositories.exchange_rate_jobs import ExchangeRateJobRepository

class Repositories:
    def __init__(self, session):
        self.exchange_rate_jobs = ExchangeRateJobRepository(session)
        self.tenants = TenantRepository(session)
        self.organizations = OrganizationRepository(session)
        self.users = UserRepository(session)
        self.employees = EmployeeRepository(session)
        self.employee_groups = EmployeeGroupRepository(session)
        self.memberships = MembershipRepository(session)

    def resource(self, kind):
        return getattr(self, kind.replace("-", "_"))
