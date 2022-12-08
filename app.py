from http import HTTPStatus

from flask import Flask, request
from to_do_api.service.user import UserService
from to_do_api.utils import response_with_status, success_response
from to_do_api.audit_logging import HTTPAuditLogger
import logging


application = Flask(__name__)
audit_logger = HTTPAuditLogger.from_env()
audit_logger.start()


logging.basicConfig(level=logging.INFO, format=f'%(levelname)-5s %(asctime)-15s [%(threadName)s] ' \
            '%(name)s:%(filename)s:%(lineno)d %(message)s')

@application.route("/users", methods=['GET', 'POST'])
@audit_logger.log_inbound(include_request_in_response=False)
def users():
    logging.debug(f"{request.path} - {request.method}")
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
    logging.info("*** APPLICATION NAME %s", application.name)
    application.run(host="0.0.0.0", port=8000)