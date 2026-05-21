"""Password hashing and verification using argon2."""
from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    return _pwd_context.needs_update(hashed_password)
