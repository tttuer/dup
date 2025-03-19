from dataclasses import dataclass


@dataclass
class User:
    id: str
    user_id: str
    password: str
    created_at: str
    updated_at: str
