
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from rest_api_server.models.base import Base, Record

class Organization(Record, Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("id", "tenant_id"),)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"),
                                           index = True)
    name: Mapped[str] = mapped_column(String(120))
