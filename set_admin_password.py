"""
Запустіть цей скрипт ONE TIME для встановлення паролів тестових користувачів.
Використання: python set_admin_password.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.auth import hash_password
from core.database import execute

users = [
    ("admin",     "admin123"),
    ("operator1", "operator123"),
    ("guest1",    "guest123"),
]

for username, password in users:
    hashed = hash_password(password)
    execute(
        "UPDATE users SET password_hash = %s WHERE username = %s",
        (hashed, username)
    )
    print(f"✓ Пароль встановлено для '{username}'")

print("\nГотово! Тепер можна входити через веб-інтерфейс.")
print("admin    / admin123")
print("operator1 / operator123")
print("guest1   / guest123")
