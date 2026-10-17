
from fastapi import HTTPException

RESOURCES = ("tenants", "organizations", "users", "employees", "employee-groups", "exchange-rate-jobs")
CRUD = ("read", "create", "update", "delete")
ROLE_ACTIONS = {
    "platform_admin": {
        "tenants": CRUD, "organizations": CRUD,
        "users": ("read", "create", "update"),
        "employees": CRUD, "employee-groups": (*CRUD, "manage_members"),
    },
    "tenant_admin": {
        "tenants": ("read", "update"), "organizations": CRUD,
        "users": ("read", "create", "update"),
        "employees": CRUD, "employee-groups": (*CRUD, "manage_members"),
    },
    "organization_admin": {
        "tenants": ("read",), "organizations": ("read", "update"),
        "users": ("read",), "employees": CRUD,
        "employee-groups": (*CRUD, "manage_members"),
    },
    "viewer": {resource: ("read",) for resource in RESOURCES},
}

for role in ("platform_admin", "tenant_admin", "organization_admin"):
    ROLE_ACTIONS[role]["exchange-rate-jobs"] = ("read", "create")

class AuthorizationService:
    def __init__(self, actor):
        self.actor = actor

    def actions(self, resource):
        return ROLE_ACTIONS.get(self.actor["role"], {}).get(resource, ())

    def require(self, resource, action):
        if action not in self.actions(resource):
            raise HTTPException(403, f"Role '{self.actor['role']}' cannot {action} {resource}")

    def visible(self, resource, item):
        actor = self.actor
        if actor["role"] == "platform_admin":
            return True
        tenant_id = item["id"] if resource == "tenants" else item.get("tenant_id")
        if tenant_id != actor["tenant_id"]:
            return False
        if not actor["organization_id"] or resource == "tenants":
            return True
        organization_id = item["id"] if resource == "organizations" else item.get("organization_id")
        return organization_id == actor["organization_id"]

    def summary(self):
        actor = self.actor
        return {
            "role": actor["role"], "tenant_id": actor["tenant_id"], "organization_id": actor["organization_id"],
            "scope": "platform" if actor["role"] == "platform_admin" else "organization" if actor["organization_id"] else "tenant",
            "resources": {resource: list(self.actions(resource)) for resource in RESOURCES},
            "restrictions": [
                "Every action is limited to the account's assigned tenant and organization scope, except platform administrators.",
                "Tenant administrators may create and deactivate lower-privilege users only; they cannot manage peer tenant administrators.",
                "Users cannot deactivate their own accounts. Accounts are deactivated rather than deleted.",
                "Role and scope cannot be changed through user PATCH. Create a user with the intended role and scope.",
                "Parent records with dependent resources cannot be deleted. Group members must belong to the same organization.",
            ],
        }
