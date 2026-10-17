
from sqlalchemy import select

from rest_api_server.models import User
from rest_api_server.repositories.base import BaseRepository

class UserRepository(BaseRepository):
    model = User

    async def by_username(self, username):
        row = await self.session.scalar(select(self.model).where(
            self.model.username == username))
        return self.values(row) if row else None
