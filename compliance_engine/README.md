# NIRIKSHA compliance rules engine

This is a Python-only legal assessment layer. It accepts structured observations
from a future Gemini/OCR adapter and returns `COMPLIANT`, `VIOLATION`, or
`UNABLE_TO_VERIFY` for every applicable (or applicability-unknown) check. It
does not inspect images, call Gemini, or modify the existing frontend.

## Evidence rule

`NOT_VISIBLE`, `UNREADABLE`, and `NOT_ASSESSED` always produce
`UNABLE_TO_VERIFY`; they can never become a missing-declaration violation.
`VIOLATION` for absence requires both `CONFIRMED_ABSENT` and
`inspected_relevant_label_surfaces=True`. An extractor should use
`CONFIRMED_ABSENT` only after it has searched the relevant visible package
surfaces.

## Example

```python
from compliance_engine import ComplianceEngine, ExtractedPackage, FieldObservation, ObservationState, PackageContext

present = lambda value: FieldObservation(ObservationState.PRESENT, value, 0.98, "front label")
package = ExtractedPackage(
    generic_name=present("Laundry detergent"),
    manufacturer=present("Example Packer Pvt Ltd, Mumbai 400001"),
    net_quantity=present("Net Qty 500 g"),
    mrp=present("MRP ₹120 inclusive of all taxes"),
    manufacture_or_pack_or_import_date=present("Packed: Aug 2026"),
    consumer_care=present("Consumer care: 1800-000-000, help@example.in"),
    context=PackageContext(is_imported=False, unit_sale_price_required=False,
                           may_become_unfit_for_human_consumption=False,
                           date_requirement_governed_by_other_law=False,
                           inspected_relevant_label_surfaces=True),
)
result = ComplianceEngine().evaluate(package)
```

`RuleSet` in `rules.py` is the controlled update point for future amendments,
exemptions, and category-specific rules. Validate the version against the latest
official gazette/Department of Consumer Affairs material before enforcement.

## Implemented legal scope

- Rule 6(1)(a), (aa), (b), (c), (d), (da), and (e), including imported-package
  importer and country-of-origin declarations;
- Rule 6(2) consumer-complaint contact details, and conditional Rules 6(7),
  6(8), 6(10), and 6(10A);
- Rule 6(1)(da), introduced by the 2017 amendment, with its other-law guard;
- Rule 6(11), only when the calling classification layer says it applies and
  neither statutory proviso removes the need for it.

The Third Amendment Rules, 2026 were reviewed: their Rule 4/Rule 27 changes
concern importer declarations at specified bonded warehouses and registration
operations, not an additional package-label field in this engine.

This is a decision-support component, not a substitute for an officer's legal
review. Its source material should be reviewed against the Department of
Consumer Affairs' [official Legal Metrology rules collection](https://consumeraffairs.gov.in/pages/legal-metrology-act), including later notifications, before production enforcement.
