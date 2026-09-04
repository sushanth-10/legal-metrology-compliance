import unittest

from database import SCHEMA_SQL
from server import _automatic_violation_complaint_data, _certificate_eligibility, _complaint_scope, _normalize_complaint_status


class RoleAndComplaintSchemaTests(unittest.TestCase):
    def test_role_and_complaint_schema_supports_organization_admin_and_status_history(self) -> None:
        self.assertIn("'organization'", SCHEMA_SQL)
        self.assertIn("'admin'", SCHEMA_SQL)
        self.assertIn("complaints", SCHEMA_SQL)
        self.assertIn("complaint_status_history", SCHEMA_SQL)
        self.assertIn("AUTO_SCAN_VIOLATION", SCHEMA_SQL)

    def test_compliant_scan_does_not_create_automatic_complaint_payload(self) -> None:
        payload = _automatic_violation_complaint_data(
            "scan-compliant",
            {"id": "org-user", "role": "organization"},
            "Verified product",
            [{"id": "net_quantity", "status": "COMPLIANT"}],
            ["scan-images/org-user/scan-compliant/front.jpg"],
        )
        self.assertIsNone(payload)

    def test_violation_scan_payload_links_scan_and_preserves_evidence(self) -> None:
        payload = _automatic_violation_complaint_data(
            "scan-violation",
            {"id": "org-user", "role": "organization", "organization_id": "org-1", "state": "Karnataka", "district": "Bengaluru", "name": "Example Org"},
            "Example chips",
            [{"id": "net_quantity", "label": "Net quantity", "status": "VIOLATION", "value": "No declaration", "explanation": "Required declaration was not verified."}],
            ["scan-images/org-user/scan-violation/front.jpg"],
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload["scan_id"], "scan-violation")
        self.assertEqual(payload["organization_id"], "org-1")
        self.assertEqual(payload["source"], "AUTO_SCAN_VIOLATION")
        self.assertIn("Net quantity", payload["complaint_description"])
        self.assertEqual(payload["evidence_images"], ["scan-images/org-user/scan-violation/front.jpg"])

    def test_admin_and_officer_status_scope_and_aliases(self) -> None:
        admin_scope, admin_params = _complaint_scope({"role": "admin", "state": "Karnataka", "district": "Bengaluru"}, requested_state="Karnataka", requested_district="Bengaluru")
        officer_scope, officer_params = _complaint_scope({"role": "officer", "state": "Karnataka", "district": "Bengaluru"})
        self.assertIn("c.state", admin_scope)
        self.assertIn("c.district", admin_scope)
        self.assertEqual(admin_params, ["Karnataka", "Bengaluru"])
        self.assertEqual(officer_params, ["Karnataka", "Bengaluru"])
        self.assertEqual(admin_scope, officer_scope)
        self.assertEqual(_normalize_complaint_status("viewed"), "VIEWED")
        self.assertEqual(_normalize_complaint_status("in-progress"), "IN_PROGRESS")
        self.assertEqual(_normalize_complaint_status("review"), "IN_PROGRESS")

    def test_certificate_requires_compliant_verified_findings_and_score(self) -> None:
        scan = {"overall_status": "COMPLIANT", "compliance_score": 96}
        self.assertEqual(_certificate_eligibility(scan, [{"status": "COMPLIANT"}])[0], True)
        self.assertEqual(_certificate_eligibility(scan, [{"status": "NOT_APPLICABLE"}, {"status": "COMPLIANT"}])[0], True)
        self.assertEqual(_certificate_eligibility({**scan, "compliance_score": 89}, [{"status": "COMPLIANT"}])[0], False)
        self.assertEqual(_certificate_eligibility(scan, [{"status": "UNABLE_TO_VERIFY"}])[0], False)
        self.assertEqual(_certificate_eligibility(scan, [{"status": "VIOLATION"}])[0], False)


if __name__ == "__main__":
    unittest.main()
