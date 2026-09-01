import unittest

from database import SCHEMA_SQL


class RoleAndComplaintSchemaTests(unittest.TestCase):
    def test_role_and_complaint_schema_supports_organization_admin_and_status_history(self) -> None:
        self.assertIn("'organization'", SCHEMA_SQL)
        self.assertIn("'admin'", SCHEMA_SQL)
        self.assertIn("complaints", SCHEMA_SQL)
        self.assertIn("complaint_status_history", SCHEMA_SQL)


if __name__ == "__main__":
    unittest.main()
