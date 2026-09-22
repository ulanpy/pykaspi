from decimal import Decimal, InvalidOperation
import re


def normalize_phone(value: str) -> str:
    """Accept local KZ mobile digits or +7/8 notation; reject query fragments."""
    if not isinstance(value, str) or not re.fullmatch(r"\+?[0-9 ()-]+", value):
        raise ValueError("Expected a Kazakhstan mobile phone number")
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10 or not digits.startswith("7"):
        raise ValueError("Expected 10 local mobile digits, optionally prefixed by +7 or 8")
    return digits


def validate_amount(value: int | float | Decimal) -> float:
    try:
        amount = Decimal(str(value))
        valid = amount.is_finite() and amount > 0 and amount % Decimal("0.01") == 0
    except InvalidOperation as exc:
        raise ValueError("Amount must be a positive number in KZT") from exc
    if not valid:
        raise ValueError("Amount must be positive, finite, with at most two decimal places")
    result = float(amount)
    if Decimal(str(result)) != amount:
        raise ValueError("Amount cannot be represented without loss")
    return result
