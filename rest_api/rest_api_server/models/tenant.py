
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from rest_api_server.models.base import Base, Record

class Tenant(Record, Base):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(120))
