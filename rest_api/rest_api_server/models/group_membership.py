
from sqlalchemy import ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from rest_api_server.models.base import Base

class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        ForeignKeyConstraint(["group_id", "organization_id"],
                             ["employee_groups.id", "employee_groups.organization_id"],
                             ondelete="CASCADE"),
        ForeignKeyConstraint(["employee_id", "organization_id"],
                             ["employees.id", "employees.organization_id"],
                             ondelete="CASCADE"),
                             )
    group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
