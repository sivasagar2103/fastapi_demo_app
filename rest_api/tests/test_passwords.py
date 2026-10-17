import pytest
from rest_api_server.utils import hash_password, verify_password, legacy_argon2
from rest_api_server.schemas import UserRegistration
from pydantic import ValidationError


def test_bcrypt_password_and_legacy_compatibility():
    password = ' Password123! '
    encoded = hash_password(password)
    assert encoded.startswith('$2b$')
    assert verify_password(password, encoded)
    assert not verify_password('wrong', encoded)
    assert not verify_password('a'*73, encoded)
    assert not verify_password(password, 'malformed')
    assert verify_password(password, legacy_argon2.hash(password))


def test_utf8_byte_limit():
    assert verify_password('é'*36, hash_password('é'*36))
    with pytest.raises(ValueError, match='72'):
        hash_password('é'*37)
    with pytest.raises(ValidationError, match='72'):
        UserRegistration(username='test.user', password='é'*37)
