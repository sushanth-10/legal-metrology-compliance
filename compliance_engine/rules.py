"""Modular declaration checks for the LMPC Rules, 2011, as amended.

This module consumes structured observations only. It never reads an image or
calls OCR/AI. Incomplete image coverage always results in UNABLE_TO_VERIFY.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from .models import AssessmentTarget, ExtractedPackage, FieldObservation, ObservationState, QuantityBasis, RuleOutcome, Status

_INDIAN_CURRENCY = re.compile(r"(?:\u20b9|rs\.?|inr)\s*\d+(?:\.\d{1,2})?", re.I)
_MRP_LABEL = re.compile(r"(?:mrp|maximum\s+retail\s+price|retail\s+sale\s+price)", re.I)
_ALL_TAXES = re.compile(r"(?:inclusive\s+of\s+all\s+taxes|incl\.?\s*(?:of\s*)?all\s+taxes)", re.I)
_DATE = re.compile(r"(?:\d{1,2}[/-]\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*[-,]?\s*\d{2,4})", re.I)
_WEIGHT = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|g|kg)\b", re.I)
_VOLUME = re.compile(r"\d+(?:\.\d+)?\s*(?:ml|l)\b", re.I)
_LENGTH = re.compile(r"\d+(?:\.\d+)?\s*(?:mm|cm|m)\b", re.I)
_AREA = re.compile(r"\d+(?:\.\d+)?\s*(?:sq\.?\s*(?:mm|cm|m)|m2|cm2)\b", re.I)
_NUMBER = re.compile(r"\d+\s*(?:nos?\.?|numbers?|pieces?|pcs?\.?|units?|pairs?|sets?)\b", re.I)
_PHONE = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{9}|(?:1800|1860)[\s-]?\d{3,4}[\s-]?\d{3,4}")
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_ADDRESS = re.compile(r"\b\d{6}\b|(?:,|;).+", re.S)


def _outcome(rule_id: str, title: str, status: Status, reference: str, explanation: str, observation: FieldObservation | None = None) -> RuleOutcome:
    evidence = (observation.evidence or observation.value or "") if observation else ""
    return RuleOutcome(rule_id, title, status, reference, explanation, evidence)


def _can_conclude_noncompliance(package: ExtractedPackage) -> bool:
    return package.context.inspected_relevant_label_surfaces


def _unverified(rule_id: str, title: str, reference: str, observation: FieldObservation | None = None) -> RuleOutcome:
    return _outcome(rule_id, title, Status.UNABLE_TO_VERIFY, reference, "Evidence is insufficient: not visible, unreadable, unassessed, or outside inspected coverage is not proof of non-compliance.", observation)


def _field_check(rule_id: str, title: str, reference: str, package: ExtractedPackage, observation: FieldObservation, validator: Callable[[str], bool]) -> RuleOutcome:
    if observation.state is ObservationState.PRESENT and observation.value and validator(observation.value):
        return _outcome(rule_id, title, Status.COMPLIANT, reference, "The required declaration is present and satisfies this check.", observation)
    if observation.state in (ObservationState.PRESENT, ObservationState.CONFIRMED_ABSENT) and _can_conclude_noncompliance(package):
        text = "The declaration is confirmed absent from inspected evidence." if observation.state is ObservationState.CONFIRMED_ABSENT else "The declaration is present but does not satisfy the required form/content."
        return _outcome(rule_id, title, Status.VIOLATION, reference, text, observation)
    return _unverified(rule_id, title, reference, observation)


def _complete_addressed_entity(value: str) -> bool:
    # Rule 6(1)(a) requires identity and address. A normalized name alone is
    # insufficient; this accepts a PIN code or multi-part address evidence.
    return len(value.strip()) >= 8 and bool(_ADDRESS.search(value))


# Rule 6(1)(a): name and address of manufacturer/packer/importer, as applicable.
def responsible_entity_check(package: ExtractedPackage) -> RuleOutcome:
    reference = "LMPC Rules, 2011, Rule 6(1)(a)"
    fields = (package.manufacturer, package.packer, package.importer)
    if any(field.state is ObservationState.PRESENT and field.value and _complete_addressed_entity(field.value) for field in fields):
        return _outcome("R6_1_A_ENTITY", "Manufacturer/packer/importer name and address", Status.COMPLIANT, reference, "A responsible entity declaration includes an identifiable name and address.")
    if _can_conclude_noncompliance(package) and all(field.state in (ObservationState.PRESENT, ObservationState.CONFIRMED_ABSENT) for field in fields):
        return _outcome("R6_1_A_ENTITY", "Manufacturer/packer/importer name and address", Status.VIOLATION, reference, "No inspected entity declaration contains both name and a verifiable address.")
    return _unverified("R6_1_A_ENTITY", "Manufacturer/packer/importer name and address", reference)


# Rule 6(1)(aa), inserted by G.S.R. 629(E) (2017): imported packages.
def imported_declaration_checks(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(1)(aa), inserted by 2017 amendment"
    if package.context.is_imported is None:
        yield _unverified("R6_1_AA_ORIGIN", "Country of origin/manufacture/assembly", reference)
    elif package.context.is_imported:
        yield _field_check("R6_1_AA_ORIGIN", "Country of origin/manufacture/assembly", reference, package, package.country_of_origin, lambda text: len(text.strip()) >= 2)
        yield _field_check("R6_1_A_IMPORTER", "Importer name and address", "LMPC Rules, 2011, Rule 6(1)(a)", package, package.importer, _complete_addressed_entity)


# Rule 6(1)(b): generic name; multipacks must state each product's name and quantity.
def product_identity_checks(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(1)(b)"
    yield _field_check("R6_1_B", "Common/generic product name", reference, package, package.generic_name, lambda text: bool(text.strip()))
    if package.context.contains_multiple_products is None:
        yield _unverified("R6_1_B_MULTIPACK", "Names and quantities of products in a multipack", reference)
    elif package.context.contains_multiple_products:
        yield _field_check("R6_1_B_MULTIPACK", "Names and quantities of products in a multipack", reference, package, package.component_names_and_quantities, lambda text: bool(re.search(r"\d", text)) and len(text.strip()) > 3)


def _quantity_matches_basis(text: str, basis: QuantityBasis | None) -> bool:
    patterns = {QuantityBasis.WEIGHT: _WEIGHT, QuantityBasis.VOLUME: _VOLUME, QuantityBasis.LENGTH: _LENGTH, QuantityBasis.AREA: _AREA, QuantityBasis.NUMBER: _NUMBER}
    return bool(patterns[basis].search(text)) if basis else bool(_WEIGHT.search(text) or _VOLUME.search(text) or _LENGTH.search(text) or _AREA.search(text) or _NUMBER.search(text))


# Rule 6(1)(c): standard unit; where sold by number, state the number in the package.
def net_quantity_check(package: ExtractedPackage) -> RuleOutcome:
    return _field_check("R6_1_C", "Net quantity and unit", "LMPC Rules, 2011, Rule 6(1)(c)", package, package.net_quantity, lambda text: _quantity_matches_basis(text, package.context.quantity_basis))


# Rule 6(1)(d): month/year of manufacture/pre-pack/import, subject to other-law exceptions.
def manufacturing_date_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    if package.context.assessment_target is AssessmentTarget.ECOMMERCE_LISTING or package.context.date_requirement_governed_by_other_law is True:
        return
    reference = "LMPC Rules, 2011, Rule 6(1)(d)"
    if package.context.date_requirement_governed_by_other_law is None:
        yield _unverified("R6_1_D", "Manufacture/pack/import month and year", reference)
    else:
        yield _field_check("R6_1_D", "Manufacture/pack/import month and year", reference, package, package.manufacture_or_pack_or_import_date, lambda text: bool(_DATE.search(text)))


# Rule 6(1)(da), inserted by G.S.R. 629(E) (2017), has an other-law exception.
def best_before_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(1)(da), inserted by 2017 amendment"
    context = package.context
    if context.date_requirement_governed_by_other_law is True:
        return
    if context.may_become_unfit_for_human_consumption is None or context.date_requirement_governed_by_other_law is None:
        yield _unverified("R6_1_DA", "Best-before/use-by/expiry date", reference)
    elif context.may_become_unfit_for_human_consumption:
        yield _field_check("R6_1_DA", "Best-before/use-by/expiry date", reference, package, package.best_before_or_use_by, lambda text: bool(_DATE.search(text)))


# Rule 6(1)(e), substituted by the 2017 amendment: Indian currency and all-taxes wording.
def mrp_check(package: ExtractedPackage) -> RuleOutcome:
    validator = lambda text: bool(_MRP_LABEL.search(text) and _INDIAN_CURRENCY.search(text) and _ALL_TAXES.search(text))
    return _field_check("R6_1_E", "MRP/retail sale price inclusive of all taxes", "LMPC Rules, 2011, Rule 6(1)(e)", package, package.mrp, validator)


def _valid_unit_price(text: str, basis: QuantityBasis | None) -> bool:
    if not (_INDIAN_CURRENCY.search(text) and re.search(r"(?:/|per)\s*", text, re.I)):
        return False
    units = {QuantityBasis.WEIGHT: r"(?:g|kg)", QuantityBasis.VOLUME: r"(?:ml|l)", QuantityBasis.LENGTH: r"(?:cm|m)", QuantityBasis.NUMBER: r"(?:number|unit|piece|pair|set)"}
    return bool(re.search(units[basis], text, re.I)) if basis in units else True


# Rule 6(11), amended in 2021/2022; no declaration where RSP equals unit price.
def unit_sale_price_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(11), as amended in 2021/2022"
    context = package.context
    # Rule 6(10)'s digital-listing obligation expressly incorporates Rule 6(1),
    # not the separate Rule 6(11) package declaration.
    if context.assessment_target is AssessmentTarget.ECOMMERCE_LISTING:
        return
    if context.unit_sale_price_governed_by_other_law is True or context.retail_sale_price_equals_unit_sale_price is True:
        return
    if context.unit_sale_price_required is None or context.retail_sale_price_equals_unit_sale_price is None or context.unit_sale_price_governed_by_other_law is None:
        yield _unverified("R6_11", "Unit sale price", reference)
    elif context.unit_sale_price_required:
        yield _field_check("R6_11", "Unit sale price", reference, package, package.unit_sale_price, lambda text: _valid_unit_price(text, context.quantity_basis))


# Rule 6(2), substituted by G.S.R. 385(E) (2015): complaint contact details.
def consumer_care_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    if package.context.assessment_target is AssessmentTarget.ECOMMERCE_LISTING:
        return
    contact = package.consumer_care
    addressed_entity_is_visible = any(
        field.state is ObservationState.PRESENT and field.value and _complete_addressed_entity(field.value)
        for field in (package.manufacturer, package.packer, package.importer)
    )
    # A label may direct the consumer to the registered-office address printed
    # in the manufacturer block. Evaluate that visible package evidence as a
    # whole; do not require the extractor to duplicate the address in both
    # fields. A phone or email is a usable complaint contact channel.
    validator = lambda text: bool((_PHONE.search(text) or _EMAIL.search(text)) and (_ADDRESS.search(text) or addressed_entity_is_visible))
    yield _field_check("R6_2", "Consumer complaint contact", "LMPC Rules, 2011, Rule 6(2), substituted by 2015 amendment", package, contact, validator)


# Rule 6(7): a package containing genetically modified food must bear "GM".
def gm_food_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(7)"
    if package.context.assessment_target is AssessmentTarget.ECOMMERCE_LISTING:
        return
    if package.context.is_genetically_modified_food is None:
        yield _unverified("R6_7_GM", "GM food declaration", reference)
    elif package.context.is_genetically_modified_food:
        yield _field_check("R6_7_GM", "GM food declaration", reference, package, package.gm_mark, lambda text: bool(re.search(r"\bGM\b", text, re.I)))


# Rule 6(8): prescribed vegetarian/non-vegetarian mark for applicable products.
def dietary_origin_mark_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(8)"
    if package.context.assessment_target is AssessmentTarget.ECOMMERCE_LISTING:
        return
    if package.context.requires_vegetarian_origin_mark is None:
        yield _unverified("R6_8_ORIGIN_MARK", "Vegetarian/non-vegetarian origin mark", reference)
    elif package.context.requires_vegetarian_origin_mark:
        yield _field_check("R6_8_ORIGIN_MARK", "Vegetarian/non-vegetarian origin mark", reference, package, package.dietary_origin_mark, lambda text: bool(text.strip()))


# Rule 6(10A), inserted by the 2026 amendment effective 1 July 2026: imported-product listing filter.
def ecommerce_filter_check(package: ExtractedPackage) -> Iterable[RuleOutcome]:
    reference = "LMPC Rules, 2011, Rule 6(10A), inserted by 2026 amendment"
    applicable = package.context.is_ecommerce_entity_offering_imported_product
    if applicable is None:
        yield _unverified("R6_10A", "E-commerce country-of-origin searchable/sortable filter", reference)
    elif applicable:
        yield _field_check("R6_10A", "E-commerce country-of-origin searchable/sortable filter", reference, package, package.ecommerce_country_of_origin_filter, lambda text: bool(re.search(r"searchable", text, re.I) and re.search(r"sortable", text, re.I)))


@dataclass(frozen=True)
class RuleSet:
    """Composition point for later gazette amendments and category-specific overlays."""

    # The Third Amendment Rules, 2026 amend Rule 4/Rule 27 operational matters;
    # they do not add a further package-label declaration checked by this ruleset.
    version: str = "LMPC-2011-label-declarations-reviewed-through-2026-third-amendment"

    def evaluate(self, package: ExtractedPackage) -> tuple[RuleOutcome, ...]:
        outcomes: list[RuleOutcome] = [responsible_entity_check(package), mrp_check(package), net_quantity_check(package)]
        outcomes.extend(imported_declaration_checks(package))
        outcomes.extend(product_identity_checks(package))
        outcomes.extend(manufacturing_date_check(package))
        outcomes.extend(best_before_check(package))
        outcomes.extend(unit_sale_price_check(package))
        outcomes.extend(consumer_care_check(package))
        outcomes.extend(gm_food_check(package))
        outcomes.extend(dietary_origin_mark_check(package))
        outcomes.extend(ecommerce_filter_check(package))
        return tuple(outcomes)
