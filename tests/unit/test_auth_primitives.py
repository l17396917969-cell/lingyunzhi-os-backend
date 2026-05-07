# tests/unit/test_auth_primitives.py
import pytest
from onto_platform.auth import (
    Scope, generate_token, hash_token, verify_token, token_prefix,
)


def test_token_format():
    t = generate_token()
    assert t.startswith("op_")
    assert len(t) > 30  # 32 random bytes -> ~43 base64url chars


def test_hash_and_verify_match():
    t = generate_token()
    h = hash_token(t)
    assert h != t
    assert verify_token(t, h) is True


def test_verify_rejects_wrong_token():
    t = generate_token()
    h = hash_token(t)
    other = generate_token()
    assert verify_token(other, h) is False


def test_token_prefix_stable_length():
    t = generate_token()
    p = token_prefix(t)
    assert len(p) == 8


def test_scope_ordering():
    assert Scope.read < Scope.editor < Scope.admin
    assert Scope.editor >= Scope.read
    assert Scope.admin >= Scope.editor
