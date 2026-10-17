
from sqlalchemy import ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from rest_api_server.models.base import Base, Record, OrganizationScoped

class Employee(Record, OrganizationScoped, Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        ForeignKeyConstraint(["organization_id", "tenant_id"],
                             ["organizations.id", "organizations.tenant_id"],
                             ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    job_title: Mapped[str] = mapped_column(String(120), default="")
