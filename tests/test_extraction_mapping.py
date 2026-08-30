import unittest

from compliance_engine import ObservationState
from server import _extract_package


class ExtractionMappingTests(unittest.TestCase):
    def test_visible_lays_style_declarations_remain_separate_and_verbatim(self) -> None:
        payload = {
            "context": {"inspected_relevant_label_surfaces": True, "quantity_basis": "WEIGHT"},
            "fields": {
                "generic_name": {"status": "VISIBLE", "value": "POTATO CHIPS", "evidence": "POTATO CHIPS", "confidence": 0.99},
                "product_name": {"status": "NOT_VISIBLE", "value": None, "evidence": ""},
                "manufacturer_details": {"status": "VISIBLE", "value": "PepsiCo India Holdings Pvt. Ltd., Noida-201301, Uttar Pradesh, India.", "evidence": "PepsiCo India Holdings Pvt. Ltd. ... Noida-201301"},
                "net_quantity": {"status": "NOT_VISIBLE", "value": None, "evidence": "Per Serve (20 g) is not a net quantity declaration."},
                "mrp": {"status": "VISIBLE", "value": "MRP ₹20.00 (INCL. OF ALL TAXES)", "evidence": "MRP ₹20.00 (INCL. OF ALL TAXES)"},
                "unit_sale_price": {"status": "VISIBLE", "value": "USP ₹1.00 PER g", "evidence": "USP ₹1.00 PER g"},
                "date_declaration": {"status": "VISIBLE", "value": "MFD.: 14/05/2024", "evidence": "MFD.: 14/05/2024"},
                "use_by": {"status": "VISIBLE", "value": "USE BY: 13/11/2024", "evidence": "USE BY: 13/11/2024"},
                "consumer_care_details": {"status": "VISIBLE", "value": "CONSUMER.FEEDBACK@PEPSICO.COM OR CALL US AT 1800 22 4020", "evidence": "CONSUMER.FEEDBACK@PEPSICO.COM OR CALL US AT 1800 22 4020"},
                "dietary_origin_mark": {"status": "VISIBLE", "value": "Green vegetarian symbol", "evidence": "Green vegetarian symbol"},
            },
        }

        package = _extract_package(payload)

        self.assertEqual(package.generic_name.value, "POTATO CHIPS")
        self.assertEqual(package.net_quantity.state, ObservationState.NOT_VISIBLE)
        self.assertEqual(package.mrp.value, "MRP ₹20.00 (INCL. OF ALL TAXES)")
        self.assertEqual(package.unit_sale_price.value, "USP ₹1.00 PER g")
        self.assertEqual(package.manufacture_or_pack_or_import_date.value, "MFD.: 14/05/2024")
        self.assertEqual(package.best_before_or_use_by.value, "USE BY: 13/11/2024")
        self.assertEqual(package.dietary_origin_mark.value, "Green vegetarian symbol")

    def test_unknown_coverage_is_not_silently_treated_as_complete(self) -> None:
        package = _extract_package({"context": {}, "fields": {}})
        self.assertFalse(package.context.inspected_relevant_label_surfaces)


if __name__ == "__main__":
    unittest.main()
