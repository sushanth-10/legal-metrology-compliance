import unittest

from compliance_engine import ComplianceEngine, ExtractedPackage, FieldObservation, ObservationState, PackageContext, QuantityBasis, Status
from compliance_engine.rules import responsible_entity_check


def present(value: str) -> FieldObservation:
    return FieldObservation(ObservationState.PRESENT, value)


class ComplianceEngineTests(unittest.TestCase):
    def test_mrp_accepts_equivalent_currency_and_tax_inclusive_formatting(self) -> None:
        for declaration in (
            "~MRP Rs. 20/- (INCL. OF ALL TAXES)",
            "MRP Rs 20/- (INCL. OF ALL TAXES)",
            "MRP R S . 20/- (INCL. OF ALL TAXES)",
            "MRP Rs. 20/- (INCL. OF ALL TAXES)",
            "MRP ₹20/- (INCL OF ALL TAXES)",
            "MRP R.S. 20.00 (INCLUSIVE OF ALL TAXES)",
            "MRP R S 20,00 (INCL. OF ALL TAXES)",
        ):
            package = ExtractedPackage(
                mrp=present(declaration),
                context=PackageContext(inspected_relevant_label_surfaces=True),
            )
            outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_E")
            self.assertEqual(outcome.status, Status.COMPLIANT, declaration)

    def test_mrp_still_requires_label_currency_and_inclusive_tax_wording(self) -> None:
        for declaration in (
            "MRP Rs. 20/-",
            "MRP 20/- (INCL. OF ALL TAXES)",
            "USP Rs. 0.64/- PER g",
        ):
            package = ExtractedPackage(
                mrp=present(declaration),
                context=PackageContext(inspected_relevant_label_surfaces=True),
            )
            outcome = next(item for item in ComplianceEngine().evaluate(package).outcomes if item.rule_id == "R6_1_E")
            self.assertEqual(outcome.status, Status.VIOLATION, declaration)

    def test_ecommerce_country_origin_filter_is_not_a_compliance_finding(self) -> None:
        package = ExtractedPackage(
            context=PackageContext(
                is_imported=True,
                inspected_relevant_label_surfaces=True,
            ),
        )
        rule_ids = {item.rule_id for item in ComplianceEngine().evaluate(package).outcomes}
        self.assertNotIn("R6_10A", rule_ids)

    def test_responsible_entity_retains_observation_provenance(self) -> None:
        package = ExtractedPackage(
            manufacturer=FieldObservation(
                ObservationState.PRESENT,
                "PepsiCo India Holdings Pvt. Ltd., Noida 201301",
                evidence="PepsiCo India Holdings Pvt. Ltd., Noida 201301",
                source_image=1,
            ),
            context=PackageContext(inspected_relevant_label_surfaces=True),
        )
        outcome = responsible_entity_check(package)
        self.assertEqual(outcome.status, Status.COMPLIANT)
        self.assertEqual(outcome.source_image, 1)
        self.assertIn("PepsiCo", outcome.evidence)

    def test_responsible_entity_can_link_repeated_name_to_contact_address(self) -> None:
        package = ExtractedPackage(
            manufacturer=FieldObservation(
                ObservationState.PRESENT,
                "Mfg. & Mkt. by: PepsiCo India Holdings Pvt. Ltd.",
                source_image=1,
            ),
            consumer_care=FieldObservation(
                ObservationState.PRESENT,
                "The Consumer Services Manager, PepsiCo India Holdings Pvt. Ltd., P.O. Box 27, Gurugram - 122002, Haryana, India.",
                source_image=1,
            ),
            context=PackageContext(inspected_relevant_label_surfaces=True),
        )
        outcome = responsible_entity_check(package)
        self.assertEqual(outcome.status, Status.COMPLIANT)
        self.assertEqual(outcome.source_image, 1)
        self.assertIn("122002", outcome.evidence)

    def test_unrelated_contact_address_does_not_complete_entity_declaration(self) -> None:
        package = ExtractedPackage(
            manufacturer=present("Mfg. & Mkt. by: PepsiCo India Holdings Pvt. Ltd."),
            consumer_care=present("Consumer care: Acme Services, Mumbai 400001; 1800 000 000"),
            context=PackageContext(inspected_relevant_label_surfaces=True),
        )
        outcome = responsible_entity_check(package)
        self.assertEqual(outcome.status, Status.UNABLE_TO_VERIFY)

    def test_lays_style_visible_evidence_is_not_misclassified(self) -> None:
        package = ExtractedPackage(
            generic_name=present("POTATO CHIPS"),
            manufacturer=present("PepsiCo India Holdings Pvt. Ltd., C-10, First Floor, Sector-1, Noida-201301, Uttar Pradesh, India."),
            net_quantity=FieldObservation(ObservationState.NOT_VISIBLE, evidence="Per Serve (20 g) is serving information, not net quantity."),
            mrp=present("MRP ₹20.00 (INCL. OF ALL TAXES)"),
            unit_sale_price=present("USP ₹1.00 PER g"),
            manufacture_or_pack_or_import_date=present("MFD.: 14/05/2024"),
            best_before_or_use_by=present("USE BY: 13/11/2024"),
            consumer_care=present("CONSUMER.FEEDBACK@PEPSICO.COM OR CALL US AT 1800 22 4020 OR WRITE TO US AT THE REGISTERED OFFICE ADDRESS MENTIONED ABOVE."),
            dietary_origin_mark=present("Green vegetarian symbol"),
            context=PackageContext(
                is_imported=False,
                may_become_unfit_for_human_consumption=True,
                date_requirement_governed_by_other_law=False,
                unit_sale_price_required=True,
                retail_sale_price_equals_unit_sale_price=False,
                unit_sale_price_governed_by_other_law=False,
                quantity_basis=QuantityBasis.WEIGHT,
                contains_multiple_products=False,
                is_genetically_modified_food=False,
                requires_vegetarian_origin_mark=True,
                inspected_relevant_label_surfaces=True,
            ),
        )
        outcomes = {item.rule_id: item for item in ComplianceEngine().evaluate(package).outcomes}
        for rule_id in ("R6_1_A_ENTITY", "R6_1_E", "R6_1_B", "R6_1_D", "R6_1_DA", "R6_11", "R6_2", "R6_8_ORIGIN_MARK"):
            self.assertEqual(outcomes[rule_id].status, Status.COMPLIANT, rule_id)
        self.assertEqual(outcomes["R6_1_C"].status, Status.UNABLE_TO_VERIFY)
        self.assertEqual(outcomes["R6_1_E"].evidence, "MRP ₹20.00 (INCL. OF ALL TAXES)")
        self.assertEqual(outcomes["R6_11"].evidence, "USP ₹1.00 PER g")

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
