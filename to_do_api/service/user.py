import json
import typing as t
import uuid

from to_do_api.dao.user import UserDAO
from to_do_api.models import User


class UserService:
    def __init__(self):
        self.__dao = UserDAO()

    def insert_user(self, json_user: dict) -> User:
        user = User(**json_user)

        user.id = uuid.uuid4()
        row_count = self.__dao.insert_user(user)

        if row_count != 1:
            raise Exception("Error inserting user")
        return user

    def list_users(self) -> t.List[User]:
        return self.__dao.list_users()