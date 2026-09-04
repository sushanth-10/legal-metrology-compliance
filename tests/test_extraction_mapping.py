import unittest

from compliance_engine import ObservationState
from server import _extract_package, _field_record, _has_structured_extraction, _result_rows


class ExtractionMappingTests(unittest.TestCase):
    def test_persisted_source_image_is_returned_to_frontend_contract(self) -> None:
        class Cursor:
            def execute(self, *_args):
                return None

            def fetchall(self):
                return [{
                    "id": 7,
                    "check_name": "R6_1_A_ENTITY",
                    "status": "COMPLIANT",
                    "extracted_value": "PepsiCo India Holdings Pvt. Ltd., Noida 201301",
                    "applicable_requirement": "Rule 6(1)(a)",
                    "explanation": "Visible declaration.",
                    "evidence": "PepsiCo India Holdings Pvt. Ltd., Noida 201301",
                    "confidence": None,
                    "source_image": 1,
                }, {
                    "id": 8,
                    "check_name": "R6_10A",
                    "status": "UNABLE_TO_VERIFY",
                    "extracted_value": None,
                    "applicable_requirement": "Legacy e-commerce metric",
                    "explanation": "Legacy row retained for auditability.",
                    "evidence": None,
                    "confidence": None,
                    "source_image": None,
                }]

        rows = _result_rows(Cursor(), "scan-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sourceImage"], 1)

    def test_visible_lays_style_declarations_remain_separate_and_verbatim(self) -> None:
        payload = {
            "context": {"inspected_relevant_label_surfaces": True, "quantity_basis": "WEIGHT"},
            "fields": {
                "generic_name": {"status": "VISIBLE", "value": "POTATO CHIPS", "evidence": "POTATO CHIPS", "confidence": 0.99},
                "product_name": {"status": "NOT_VISIBLE", "value": None, "evidence": ""},
                "manufacturer_details": {"status": "VISIBLE", "value": "PepsiCo India Holdings Pvt. Ltd., Noida-201301, Uttar Pradesh, India.", "evidence": "PepsiCo India Holdings Pvt. Ltd. ... Noida-201301", "source_image_index": 1, "bounding_box": {"x": 12, "y": 25, "w": 70, "h": 20}},
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
        self.assertEqual(package.manufacturer.source_image, 1)
        self.assertEqual(package.manufacturer.bounding_box, {"x": 12, "y": 25, "w": 70, "h": 20})
        persisted = _field_record(package.manufacturer)
        self.assertEqual(persisted["source_image_index"], 1)
        self.assertEqual(persisted["bounding_box"]["w"], 70)
        self.assertEqual(package.manufacture_or_pack_or_import_date.value, "MFD.: 14/05/2024")
        self.assertEqual(package.best_before_or_use_by.value, "USE BY: 13/11/2024")
        self.assertEqual(package.dietary_origin_mark.value, "Green vegetarian symbol")

    def test_unknown_coverage_is_not_silently_treated_as_complete(self) -> None:
        package = _extract_package({"context": {}, "fields": {}})
        self.assertFalse(package.context.inspected_relevant_label_surfaces)

    def test_nested_gemini_envelope_keeps_the_richest_extraction(self) -> None:
        package = _extract_package({
            "response": {
                "data": {
                    "result": {
                        "fields": {
                            "generic_name": {"status": "VISIBLE", "value": "BISCUITS", "evidence": "BISCUITS"},
                            "mrp": {"status": "VISIBLE", "value": "MRP Rs. 50.00 (INCL. OF ALL TAXES)", "evidence": "MRP Rs. 50.00 (INCL. OF ALL TAXES)"},
                        },
                        "context": {"inspected_relevant_label_surfaces": True},
                    },
                },
            },
        })

        self.assertEqual(package.generic_name.value, "BISCUITS")
        self.assertEqual(package.mrp.value, "MRP Rs. 50.00 (INCL. OF ALL TAXES)")
        self.assertTrue(package.context.inspected_relevant_label_surfaces)

    def test_mrp_promotes_complete_existing_evidence_when_value_is_only_parsed_price(self) -> None:
        declaration = "MRP ₹ 50.00 (INCL. OF ALL TAXES)"
        package = _extract_package({
            "context": {"inspected_relevant_label_surfaces": True},
            "fields": {
                "mrp": {
                    "status": "VISIBLE",
                    "value": "50.00",
                    "evidence": declaration,
                    "source_image_index": 1,
                },
            },
        })

        self.assertEqual(package.mrp.value, declaration)
        self.assertEqual(package.mrp.source_image, 1)

    def test_flat_camel_case_extraction_is_mapped_without_ai_or_ocr(self) -> None:
        package = _extract_package({
            "context": {"inspectedRelevantLabelSurfaces": True, "quantityBasis": "WEIGHT"},
            "genericName": {"status": "DETECTED", "value": "BISCUITS", "evidence": "BISCUITS", "sourceImageIndex": 0},
            "mrp": {"status": "VISIBLE", "value": "MRP Rs. 50/- (INCL. OF ALL TAXES)", "evidence": "MRP Rs. 50/- (INCL. OF ALL TAXES)", "sourceImageIndex": 1},
        })

        self.assertEqual(package.generic_name.value, "BISCUITS")
        self.assertEqual(package.generic_name.source_image, 0)
        self.assertEqual(package.mrp.source_image, 1)
        self.assertTrue(package.context.inspected_relevant_label_surfaces)

    def test_serialized_nested_extraction_is_unwrapped(self) -> None:
        payload = {
            "data": '{"fields":{"manufacturer_details":{"status":"VISIBLE","value":"Acme Pvt. Ltd., Delhi 110001","evidence":"Acme Pvt. Ltd., Delhi 110001","source_image_number":1}},"context":{"inspected_relevant_label_surfaces":true}}'
        }

        self.assertTrue(_has_structured_extraction(payload))
        package = _extract_package(payload)
        self.assertEqual(package.manufacturer.value, "Acme Pvt. Ltd., Delhi 110001")
        self.assertEqual(package.manufacturer.source_image, 0)

    def test_named_field_list_is_mapped_without_inventing_values(self) -> None:
        package = _extract_package({
            "observations": [
                {"name": "MRP/retail sale price inclusive of all taxes", "status": "VISIBLE", "value": "MRP Rs. 50/- (INCL. OF ALL TAXES)"},
                {"field": "net_quantity_and_unit", "value": "Net Weight 200 g"},
            ],
            "context": {"quantity_basis": "WEIGHT"},
        })

        self.assertEqual(package.mrp.value, "MRP Rs. 50/- (INCL. OF ALL TAXES)")
        self.assertEqual(package.net_quantity.value, "Net Weight 200 g")

    def test_unstructured_model_json_is_not_treated_as_a_valid_extraction(self) -> None:
        self.assertFalse(_has_structured_extraction({"status": "ok", "summary": "done"}))


if __name__ == "__main__":
    unittest.main()
