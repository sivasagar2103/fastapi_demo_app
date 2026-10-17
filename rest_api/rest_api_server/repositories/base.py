
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository:
    model = None

    def __init__(self, session: AsyncSession):
        self.session = session

    def values(self, row):
        return {column.key: getattr(row, column.key) 
                for column in self.model.__table__.columns}

    async def get(self, record_id):
        row = await self.session.get(self.model, record_id)
        return self.values(row) if row else None

    async def list(self, actor = None, offset = 0, limit = None, newest_first=False):
        statement = select(self.model)
        if actor and actor["role"] != "platform_admin":
            tenant_column = self.model.id if self.model.__tablename__ == "tenants" else self.model.tenant_id
            statement = statement.where(tenant_column == actor["tenant_id"])
            if actor["organization_id"]:
                if self.model.__tablename__ == "organizations":
                    statement = statement.where(self.model.id == actor["organization_id"])
                elif self.model.__tablename__ != "tenants":
                    statement = statement.where(self.model.organization_id == actor["organization_id"])
        ordering = (self.model.created_at.desc(), self.model.id.desc()) if newest_first else (self.model.created_at, self.model.id)
        statement = statement.order_by(*ordering).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return [self.values(row) for row in (await self.session.scalars(statement)).all()]

    async def create(self, data):
        row = self.model(**data)
        self.session.add(row)
        await self.session.flush()
        return self.values(row)

    async def update(self, record_id, data):
        row = await self.session.get(self.model, record_id)
        for key, value in data.items():
            setattr(row, key, value)
        await self.session.flush()
        return self.values(row)

    async def delete(self, record_id):
        row = await self.session.get(self.model, record_id)
        await self.session.delete(row)
        await self.session.flush()
