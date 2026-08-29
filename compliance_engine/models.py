"""Stable data contract between an extractor and the legal rules.

An OCR/AI adapter should convert its output into these plain Python objects.  This
module deliberately does not import or call a model, OCR library, or web service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    COMPLIANT = "COMPLIANT"
    VIOLATION = "VIOLATION"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    OFFICER_REVIEW_REQUIRED = "OFFICER_REVIEW_REQUIRED"


class ObservationState(str, Enum):
    """What the extractor can actually support about a field.

    ``NOT_VISIBLE`` and ``UNREADABLE`` are intentionally different from
    ``CONFIRMED_ABSENT``.  Only the latter can support a missing-declaration
    violation, and then only when the relevant label surface was inspected.
    """

    PRESENT = "PRESENT"
    CONFIRMED_ABSENT = "CONFIRMED_ABSENT"
    NOT_VISIBLE = "NOT_VISIBLE"
    UNREADABLE = "UNREADABLE"
    NOT_ASSESSED = "NOT_ASSESSED"


class QuantityBasis(str, Enum):
    """How the commodity is sold; used only to select the applicable rule."""

    WEIGHT = "WEIGHT"
    VOLUME = "VOLUME"
    LENGTH = "LENGTH"
    AREA = "AREA"
    NUMBER = "NUMBER"


class AssessmentTarget(str, Enum):
    """Whether evidence is a physical package or a Rule 6(10) listing."""

    PACKAGE_LABEL = "PACKAGE_LABEL"
    ECOMMERCE_LISTING = "ECOMMERCE_LISTING"


@dataclass(frozen=True)
class FieldObservation:
    """Verbatim, label/listing-level extraction for one declaration.

    For checks such as MRP wording, ``value`` must retain the declaration text,
    not only a normalized price or a value inferred by an upstream model.
    """
    state: ObservationState = ObservationState.NOT_ASSESSED
    value: Optional[str] = None
    confidence: Optional[float] = None
    evidence: str = ""


@dataclass(frozen=True)
class PackageContext:
    """Facts supplied outside individual label fields.

    Set a conditional requirement to ``None`` when it is unknown; the engine
    will report UNABLE_TO_VERIFY rather than guessing that the requirement
    applies or does not apply.
    """

    is_imported: Optional[bool] = None
    may_become_unfit_for_human_consumption: Optional[bool] = None
    date_requirement_governed_by_other_law: Optional[bool] = None
    unit_sale_price_required: Optional[bool] = None
    retail_sale_price_equals_unit_sale_price: Optional[bool] = None
    unit_sale_price_governed_by_other_law: Optional[bool] = None
    quantity_basis: Optional[QuantityBasis] = None
    contains_multiple_products: Optional[bool] = None
    is_genetically_modified_food: Optional[bool] = None
    requires_vegetarian_origin_mark: Optional[bool] = None
    assessment_target: AssessmentTarget = AssessmentTarget.PACKAGE_LABEL
    is_ecommerce_entity_offering_imported_product: Optional[bool] = None
    inspected_relevant_label_surfaces: bool = False


@dataclass(frozen=True)
class ExtractedPackage:
    """Package facts from an upstream extractor; no legal conclusion belongs here."""

    generic_name: FieldObservation = field(default_factory=FieldObservation)
    manufacturer: FieldObservation = field(default_factory=FieldObservation)
    packer: FieldObservation = field(default_factory=FieldObservation)
    importer: FieldObservation = field(default_factory=FieldObservation)
    country_of_origin: FieldObservation = field(default_factory=FieldObservation)
    net_quantity: FieldObservation = field(default_factory=FieldObservation)
    mrp: FieldObservation = field(default_factory=FieldObservation)
    unit_sale_price: FieldObservation = field(default_factory=FieldObservation)
    manufacture_or_pack_or_import_date: FieldObservation = field(default_factory=FieldObservation)
    best_before_or_use_by: FieldObservation = field(default_factory=FieldObservation)
    consumer_care: FieldObservation = field(default_factory=FieldObservation)
    component_names_and_quantities: FieldObservation = field(default_factory=FieldObservation)
    gm_mark: FieldObservation = field(default_factory=FieldObservation)
    dietary_origin_mark: FieldObservation = field(default_factory=FieldObservation)
    ecommerce_country_of_origin_filter: FieldObservation = field(default_factory=FieldObservation)
    context: PackageContext = field(default_factory=PackageContext)


@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    title: str
    status: Status
    legal_reference: str
    explanation: str
    evidence: str = ""


@dataclass(frozen=True)
class ComplianceResult:
    outcomes: tuple[RuleOutcome, ...]

    @property
    def overall_status(self) -> Status:
        if any(item.status is Status.VIOLATION for item in self.outcomes):
            return Status.VIOLATION
        if any(item.status is Status.OFFICER_REVIEW_REQUIRED for item in self.outcomes):
            return Status.OFFICER_REVIEW_REQUIRED
        if any(item.status is Status.UNABLE_TO_VERIFY for item in self.outcomes):
            return Status.UNABLE_TO_VERIFY
        if any(item.status is Status.NOT_APPLICABLE for item in self.outcomes):
            return Status.NOT_APPLICABLE
        return Status.COMPLIANT
