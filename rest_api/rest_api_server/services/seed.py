"""Explicit, idempotent local-demo bootstrap."""
from starlette.concurrency import run_in_threadpool
from rest_api_server.utils import hash_password

async def seed(repo, password):
    if await repo.users.list(limit=1):
        return
    if not password or len(password) < 12:
        raise ValueError("SEED_DEMO requires DEMO_PASSWORD of at least 12 characters")
    tenant = await repo.resource("tenants").create({"name": "Acme"})
    org = await repo.resource("organizations").create({"name": "Engineering", "tenant_id": tenant["id"]})
    for username, role, tid, oid in [
        ("platform.admin", "platform_admin", None, None),
        ("tenant.admin", "tenant_admin", tenant["id"], None),
        ("org.admin", "organization_admin", tenant["id"], org["id"]),
        ("viewer", "viewer", tenant["id"], org["id"])]:
        await repo.resource("users").create({"username": username, "role": role, "tenant_id": tid,
            "organization_id": oid, "active": True, "password_hash": await run_in_threadpool(hash_password, password)})
    employee = await repo.resource("employees").create({"name": "Alex Demo", "email": "alex@example.com", "job_title": "Engineer", "tenant_id": tenant["id"], "organization_id": org["id"]})
    group = await repo.resource("employee-groups").create({"name": "API Team", "tenant_id": tenant["id"], "organization_id": org["id"]})
    await repo.memberships.add(group["id"], employee["id"], org["id"])
