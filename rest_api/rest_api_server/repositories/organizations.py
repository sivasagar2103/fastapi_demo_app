
from rest_api_server.models import Organization
from rest_api_server.repositories.base import BaseRepository

class OrganizationRepository(BaseRepository):
    model = Organization
