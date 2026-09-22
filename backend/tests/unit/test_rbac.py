"""Unit tests for RBAC — role hierarchy and permission checks."""

from sangam_mw.rbac.permissions import (
    Permission,
    Role,
    _ROLE_PERMISSIONS as ROLE_PERMISSIONS,
    has_permission,
)


class TestRoleHierarchy:
    def test_admin_has_all_permissions(self):
        for perm in Permission:
            assert has_permission("admin", perm), f"admin missing {perm}"

    def test_viewer_cannot_write(self):
        write_perms = [
            Permission.FLOW_CREATE, Permission.FLOW_UPDATE, Permission.FLOW_DELETE,
            Permission.CONNECTION_CREATE, Permission.CONNECTION_UPDATE, Permission.CONNECTION_DELETE,
            Permission.USER_MANAGE,
        ]
        for perm in write_perms:
            assert not has_permission("viewer", perm), f"viewer should NOT have {perm}"

    def test_viewer_can_read_flows_and_executions(self):
        # Viewer only has FLOW_READ, EXECUTION_READ, CONNECTION_READ
        assert has_permission("viewer", Permission.FLOW_READ)
        assert has_permission("viewer", Permission.EXECUTION_READ)
        assert has_permission("viewer", Permission.CONNECTION_READ)

    def test_viewer_cannot_read_users_or_audit(self):
        # USER_READ and AUDIT_READ are developer+ only
        assert not has_permission("viewer", Permission.USER_READ)
        assert not has_permission("viewer", Permission.AUDIT_READ)

    def test_developer_can_create_flows(self):
        assert has_permission("developer", Permission.FLOW_CREATE)
        assert has_permission("developer", Permission.FLOW_UPDATE)
        assert has_permission("developer", Permission.CONNECTION_CREATE)

    def test_developer_can_read_users(self):
        assert has_permission("developer", Permission.USER_READ)

    def test_developer_cannot_manage_users(self):
        assert not has_permission("developer", Permission.USER_MANAGE)

    def test_operator_can_trigger_executions(self):
        assert has_permission("operator", Permission.EXECUTION_TRIGGER)
        assert has_permission("operator", Permission.EXECUTION_CANCEL)

    def test_operator_cannot_delete_flows(self):
        assert not has_permission("operator", Permission.FLOW_DELETE)

    def test_operator_cannot_read_users(self):
        assert not has_permission("operator", Permission.USER_READ)

    def test_unknown_role_denied(self):
        # Unknown role → ValueError → returns False
        assert not has_permission("unknown_role", Permission.FLOW_READ)
        assert not has_permission("unknown_role", Permission.FLOW_CREATE)

    def test_permission_enum_completeness(self):
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        for perm in Permission:
            assert perm in admin_perms, f"Permission {perm} not in admin set"

    def test_admin_is_superset_of_developer(self):
        admin = ROLE_PERMISSIONS[Role.ADMIN]
        developer = ROLE_PERMISSIONS[Role.DEVELOPER]
        assert developer.issubset(admin)

    def test_developer_is_superset_of_operator(self):
        developer = ROLE_PERMISSIONS[Role.DEVELOPER]
        operator = ROLE_PERMISSIONS[Role.OPERATOR]
        assert operator.issubset(developer)
