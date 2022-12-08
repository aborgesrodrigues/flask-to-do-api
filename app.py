from http import HTTPStatus

from flask import Flask, request
from to_do_api.service.user import UserService
from to_do_api.utils import response_with_status, success_response

application = Flask(__name__)

@application.route("/users", methods=['GET', 'POST'])
def users():
    try:
        user_service = UserService()
        if request.method == "POST":
            user = request.get_json()
            response = user_service.insert_user(user)

            # make json serializable
            response = response.__dict__
        elif request.method == "GET":
            response = user_service.list_users()

            # make json serializable
            response = [user.__dict__ for user in response]

        return success_response({"Result": response})
    except Exception as ex:
        return response_with_status(ex, HTTPStatus.INTERNAL_SERVER_ERROR)


if __name__ == "__main__":
    print(__name__)
    application.run(host="0.0.0.0", port=8000)