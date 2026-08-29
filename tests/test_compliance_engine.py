import unittest

from compliance_engine import ComplianceEngine, ExtractedPackage, FieldObservation, ObservationState, PackageContext, QuantityBasis, Status


def present(value: str) -> FieldObservation:
    return FieldObservation(ObservationState.PRESENT, value)


class ComplianceEngineTests(unittest.TestCase):
    def test_complete_domestic_package_is_compliant_for_applicable_checks(self) -> None:
        package = ExtractedPackage(
            generic_name=present("Laundry detergent"),
            manufacturer=present("Acme Packer Pvt Ltd, Mumbai 400001"),
            net_quantity=present("Net Qty 500 g"),
            mrp=present("MRP Rs. 120.00 inclusive of all taxes"),
            manufacture_or_pack_or_import_date=present("Packed Aug 2026"),
            consumer_care=present("Consumer care: Acme, Mumbai 400001; 1800 000 000; help@acme.in"),
            context=PackageContext(
                is_imported=False,
                may_become_unfit_for_human_consumption=False,
                date_requirement_governed_by_other_law=False,
                unit_sale_price_required=False,
                retail_sale_price_equals_unit_sale_price=False,
                unit_sale_price_governed_by_other_law=False,
                contains_multiple_products=False,
                is_genetically_modified_food=False,
                requires_vegetarian_origin_mark=False,
                is_ecommerce_entity_offering_imported_product=False,
                inspected_relevant_label_surfaces=True,
            ),
        )
        result = ComplianceEngine().evaluate(package)
        self.assertEqual(result.overall_status, Status.COMPLIANT)

    def test_not_visible_is_never_an_absence_violation(self) -> None:
        package = ExtractedPackage(
            generic_name=FieldObservation(ObservationState.NOT_VISIBLE),
            context=PackageContext(inspected_relevant_label_surfaces=True),
        )
        outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_B")
        self.assertEqual(outcome.status, Status.UNABLE_TO_VERIFY)

    def test_confirmed_absence_on_inspected_surfaces_is_violation(self) -> None:
        package = ExtractedPackage(
            generic_name=FieldObservation(ObservationState.CONFIRMED_ABSENT),
            context=PackageContext(inspected_relevant_label_surfaces=True),
        )
        outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_B")
        self.assertEqual(outcome.status, Status.VIOLATION)

    def test_imported_package_requires_origin_and_importer(self) -> None:
        package = ExtractedPackage(
            importer=present("Acme Imports, Delhi 110001"),
            country_of_origin=present("Japan"),
            context=PackageContext(is_imported=True, inspected_relevant_label_surfaces=True),
        )
        outcomes = {item.rule_id: item.status for item in ComplianceEngine().evaluate(package).outcomes}
        self.assertEqual(outcomes["R6_1_A_IMPORTER"], Status.COMPLIANT)
        self.assertEqual(outcomes["R6_1_AA_ORIGIN"], Status.COMPLIANT)

    def test_partial_coverage_does_not_turn_bad_mrp_text_into_violation(self) -> None:
        package = ExtractedPackage(
            mrp=present("MRP Rs. 120"),
            context=PackageContext(inspected_relevant_label_surfaces=False),
        )
        outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_E")
        self.assertEqual(outcome.status, Status.UNABLE_TO_VERIFY)

    def test_complete_coverage_detects_mrp_without_all_taxes_wording(self) -> None:
        package = ExtractedPackage(
            mrp=present("MRP Rs. 120"),
            context=PackageContext(inspected_relevant_label_surfaces=True),
        )
        outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_E")
        self.assertEqual(outcome.status, Status.VIOLATION)

    def test_number_sold_commodity_requires_number_representation(self) -> None:
        package = ExtractedPackage(
            net_quantity=present("Net quantity: 250 g"),
            context=PackageContext(quantity_basis=QuantityBasis.NUMBER, inspected_relevant_label_surfaces=True),
        )
        outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_C")
        self.assertEqual(outcome.status, Status.VIOLATION)


if __name__ == "__main__":
    unittest.main()
