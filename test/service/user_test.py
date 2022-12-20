import pytest
from to_do_api.service.user import UserService

@pytest.fixture()
def service(mocker):
    service = UserService()

    yield service

@pytest.mark.usefixtures("service")
def test_insert_user(mocker, service):
    user = {
        "id": "",
        "username": "username1",
        "name": "Name 1"
    }

    # test success case
    mocker.patch("to_do_api.dao.user.UserDAO.insert_user", lambda p1, p2: 1)

    new_user = service.insert_user(user)
    
    assert user["id"] != new_user.id

    # test fail case 1
    mocker.patch("to_do_api.dao.user.UserDAO.insert_user", lambda p1, p2: 0)

    with pytest.raises(Exception):
        service.insert_user(user)

    # test fail case 2
    mocker.patch("to_do_api.dao.user.UserDAO.insert_user", lambda p1, p2: 2)

    with pytest.raises(Exception):
        service.insert_user(user)
    