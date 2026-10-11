import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_blank_jwt_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(JWT_SECRET="   ")


def test_short_jwt_secret_is_rejected():
    with pytest.raises(ValidationError):
        Settings(JWT_SECRET="too-short-for-hs256")
