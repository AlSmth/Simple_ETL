import re


def normalize_phone(raw: str) -> str | None:
    """Возвращает номер только из цифр в международном формате (по умолчанию Армения, +374)."""
    raw = raw.strip()
    if not re.fullmatch(r"[+\d\s()\-.]+", raw):
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    if len(digits) == 8:  # 91123456
        digits = "374" + digits
    elif len(digits) == 9 and digits.startswith("0"):  # 091123456
        digits = "374" + digits[1:]
    return digits if 8 <= len(digits) <= 15 else None
