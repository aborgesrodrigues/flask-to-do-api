import uuid
from enum import Enum


class User:
    def __init__(self, id: str, name: str, username: str):
        self.id = id
        self.name = name
        self.username = username


class TaskState(Enum):
    TO_DO = 1
    DOING = 2
    DONE = 3


class Task:
    def __init__(self, description: str, user_id: str, state: TaskState):
        self.id = uuid.uuid4()
        self.description = description
        self.state = state
        self.user_id = user_id
