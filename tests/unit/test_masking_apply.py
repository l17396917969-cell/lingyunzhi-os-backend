# tests/unit/test_masking_apply.py
import pytest
from onto_platform.proto_models import MaskingStrategy
from onto_platform.connections.masking import apply_mask


@pytest.mark.parametrize("strategy,inp,expected", [
    (MaskingStrategy.MASK_NONE, "abc", "abc"),
    (MaskingStrategy.MASK_NULLIFY, "abc", None),
    (MaskingStrategy.MASK_NULLIFY, 123, None),
    (MaskingStrategy.MASK_REDACT_FULL, "abc", "***"),
    (MaskingStrategy.MASK_REDACT_FULL, 12.5, "***"),
    (MaskingStrategy.SHOW_LAST_4, "1234567890", "******7890"),
    (MaskingStrategy.SHOW_LAST_4, "abc", None),  # too short
    (MaskingStrategy.SHOW_FIRST_2, "alice@example.com", "al****"),
    (MaskingStrategy.SHOW_FIRST_2, "x", None),
    (MaskingStrategy.MASK_EMAIL_DOMAIN, "alice@example.com", "alice@***"),
    (MaskingStrategy.MASK_EMAIL_DOMAIN, "no-at-sign", None),
    (MaskingStrategy.MASK_EMAIL_USER, "alice@example.com", "***@example.com"),
    (MaskingStrategy.MASK_PHONE_MIDDLE, "13912345678", "139****5678"),
    (MaskingStrategy.MASK_PHONE_MIDDLE, "12345", None),  # too short
    (MaskingStrategy.MASK_NULLIFY, None, None),
])
def test_apply_mask(strategy, inp, expected):
    assert apply_mask(inp, strategy) == expected
