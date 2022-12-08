import typing as t

from to_do_api.models import User

from to_do_api.dao.dao import DAO


class UserDAO(DAO):
    def __init__(self):
        super().__init__()

    def insert_user(self, user: User) -> int:
        return self.execute("INSERT INTO public.user(id, username, name) VALUES(%s,%s,%s)", (user.id, user.username, user.name))

    def list_users(self) -> t.List[User]:
        users = self.fetch_all("SELECT id, name, username FROM public.user")
        users = [User(user[0], user[1], user[2]) for user in users]
        return users