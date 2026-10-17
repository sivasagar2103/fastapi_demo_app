from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, Integer, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column
from rest_api_server.models.base import Base, Record

class ExchangeRateJob(Record, Base):
    __tablename__ = "exchange_rate_jobs"
    __table_args__ = (ForeignKeyConstraint(["organization_id", "tenant_id"], ["organizations.id", "organizations.tenant_id"], ondelete="RESTRICT"),)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    base_currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[float | None] = mapped_column(Float)
    lease_until: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[str | None] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(String(300))
    result: Mapped[dict | None] = mapped_column(JSON)
