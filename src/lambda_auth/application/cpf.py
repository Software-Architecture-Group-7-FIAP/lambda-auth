"""Normalização e validação local de CPF."""

import re


def normalize_valid_cpf(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 32:
        return None
    if not re.fullmatch(r"[0-9.\-\s]+", value):
        return None

    cpf = re.sub(r"[^0-9]", "", value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return None

    digits = tuple(int(digit) for digit in cpf)
    for position in (9, 10):
        weighted_sum = sum(digits[index] * (position + 1 - index) for index in range(position))
        remainder = (weighted_sum * 10) % 11
        expected_digit = 0 if remainder == 10 else remainder
        if digits[position] != expected_digit:
            return None

    return cpf
