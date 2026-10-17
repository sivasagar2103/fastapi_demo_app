
from rest_api_server.models import Employee
from rest_api_server.repositories.base import BaseRepository

class EmployeeRepository(BaseRepository):
    model = Employee
