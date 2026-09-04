"""Modular declaration checks for the LMPC Rules, 2011, as amended.

This module consumes structured observations only. It never reads an image or
calls OCR/AI. Incomplete image coverage always results in UNABLE_TO_VERIFY.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from .models import AssessmentTarget, ExtractedPackage, FieldObservation, ObservationState, QuantityBasis, RuleOutcome, Status

# Rule 6(1)(e) permits the amount to be prefixed by either the rupee sign or
# the printed ``Rs.`` abbreviation. Accept common OCR spacing/punctuation
# variants without accepting a bare number as an MRP declaration.
_INDIAN_CURRENCY = re.compile(r"(?:\u20b9|r\s*\.?\s*s|rs|inr)\s*\.?\s*[:.]?\s*\d+(?:[.,]\d{1,2})?", re.I)
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
    return RuleOutcome(
        rule_id,
        title,
        status,
        reference,
        explanation,
        evidence,
        observation.source_image if observation else None,
        observation.source_image_ref if observation else None,
        observation.bounding_box if observation else None,
    )


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


def _entity_name_tokens(value: str) -> set[str]:
    generic = {
        "address", "by", "company", "india", "importer", "limited", "ltd",
        "manufactured", "manufacturer", "marketed", "mfg", "mkt", "packer",
        "pvt", "the", "and",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", value.lower())
        if token not in generic
    }


def _entity_with_related_address(entity: FieldObservation, contact: FieldObservation) -> FieldObservation | None:
    """Join split but explicitly repeated package declarations.

    Some packages print the legal entity beside ``Mfg. & Mkt. by`` and print
    that same entity again above its consumer-services postal address.  Treat
    this as one evidence-backed declaration only when the address is present
    and every distinctive entity token is repeated in the contact block.
    """
    if (
        entity.state is not ObservationState.PRESENT
        or not entity.value
        or contact.state is not ObservationState.PRESENT
        or not contact.value
        or not _complete_addressed_entity(contact.value)
    ):
        return None
    tokens = _entity_name_tokens(entity.value)
    if not tokens or not tokens.issubset(_entity_name_tokens(contact.value)):
        return None
    same_image = entity.source_image is not None and entity.source_image == contact.source_image
    return FieldObservation(
        state=ObservationState.PRESENT,
        value=f"{entity.value} :: Related address/contact declaration: {contact.value}",
        confidence=max(entity.confidence or 0.0, contact.confidence or 0.0) or None,
        evidence=f"{entity.evidence or entity.value} :: Related address/contact declaration: {contact.evidence or contact.value}",
        source_image=entity.source_image if same_image else None,
        source_image_ref=entity.source_image_ref if same_image else None,
        bounding_box=entity.bounding_box if same_image else None,
    )


# Rule 6(1)(a): name and address of manufacturer/packer/importer, as applicable.
def responsible_entity_check(package: ExtractedPackage) -> RuleOutcome:
    reference = "LMPC Rules, 2011, Rule 6(1)(a)"
    related_manufacturer = _entity_with_related_address(package.manufacturer, package.consumer_care)
    fields = [package.manufacturer, package.packer, package.importer]
    if related_manufacturer:
        fields.append(related_manufacturer)
    complete_field = next((field for field in fields if field.state is ObservationState.PRESENT and field.value and _complete_addressed_entity(field.value)), None)
    if complete_field:
        return _outcome("R6_1_A_ENTITY", "Manufacturer/packer/importer name and address", Status.COMPLIANT, reference, "A responsible entity declaration includes an identifiable name and address.", complete_field)
    if _can_conclude_noncompliance(package) and all(field.state in (ObservationState.PRESENT, ObservationState.CONFIRMED_ABSENT) for field in fields):
        evidence_field = next((field for field in fields if field.state is ObservationState.PRESENT), None)
        return _outcome("R6_1_A_ENTITY", "Manufacturer/packer/importer name and address", Status.VIOLATION, reference, "No inspected entity declaration contains both name and a verifiable address.", evidence_field)
    evidence_field = next((field for field in fields if field.state is ObservationState.PRESENT), None)
    return _unverified("R6_1_A_ENTITY", "Manufacturer/packer/importer name and address", reference, evidence_field)


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
    observation = package.mrp
    if observation.state is ObservationState.PRESENT:
        # The extractor may place the full printed declaration in ``evidence``
        # while ``value`` contains only a parsed price. Validate the complete
        # existing evidence in that case; do not infer or synthesize text.
        if is_valid_mrp_declaration(observation.value or ""):
            return _outcome("R6_1_E", "MRP/retail sale price inclusive of all taxes", Status.COMPLIANT, "LMPC Rules, 2011, Rule 6(1)(e)", "The required declaration is present and satisfies this check.", observation)
        if is_valid_mrp_declaration(observation.evidence or ""):
            evidence_observation = FieldObservation(
                state=observation.state,
                value=observation.evidence,
                confidence=observation.confidence,
                evidence=observation.evidence,
                source_image=observation.source_image,
                source_image_ref=observation.source_image_ref,
                bounding_box=observation.bounding_box,
            )
            return _outcome("R6_1_E", "MRP/retail sale price inclusive of all taxes", Status.COMPLIANT, "LMPC Rules, 2011, Rule 6(1)(e)", "The required declaration is present and satisfies this check.", evidence_observation)

    def validator(text: str) -> bool:
        return is_valid_mrp_declaration(text)

    return _field_check("R6_1_E", "MRP/retail sale price inclusive of all taxes", "LMPC Rules, 2011, Rule 6(1)(e)", package, observation, validator)


def is_valid_mrp_declaration(text: str) -> bool:
    """Return whether extracted MRP text contains all required components."""
    # OCR commonly inserts spaces into ``R.S.``/``INCL.`` or uses a comma
    # as the decimal separator. Normalize only those harmless forms; the MRP
    # label, currency amount, and inclusive-tax wording remain independently
    # required.
    normalized = " ".join(text.replace("\u00a0", " ").split())
    return bool(_MRP_LABEL.search(normalized) and _INDIAN_CURRENCY.search(normalized) and _ALL_TAXES.search(normalized))


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
        return tuple(outcomes)
