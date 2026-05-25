"""
Auth module for NiftyNinety.
Handles secure password hashing and verification.
"""

import hashlib
import os

def hash_password(password: str, salt: bytes = None) -> str:
    """Hashes a password using PBKDF2 HMAC SHA256."""
    if salt is None:
        salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + pwd_hash.hex()

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verifies a password against the stored hash."""
    try:
        salt_hex, hash_hex = stored_password.split(':')
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return pwd_hash.hex() == hash_hex
    except Exception:
        return False

def authenticate_user(email: str, password: str) -> bool:
    from database import get_user_by_email
    user = get_user_by_email(email)
    if user:
        return verify_password(user['password_hash'], password)
    return False

def register_user(name: str, email: str, password: str):
    from database import get_connection
    import psycopg2
    hashed_pwd = hash_password(password)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
            """, (name, email, hashed_pwd))
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise ValueError("Email already registered.")
    finally:
        conn.close()
