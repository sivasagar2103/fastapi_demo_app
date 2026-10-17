
from rest_api_server.models import EmployeeGroup
from rest_api_server.repositories.base import BaseRepository

class EmployeeGroupRepository(BaseRepository):
    model = EmployeeGroup
