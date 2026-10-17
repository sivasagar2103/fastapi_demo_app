
from rest_api_server.models import Tenant
from rest_api_server.repositories.base import BaseRepository

class TenantRepository(BaseRepository):
    model = Tenant
