from http import HTTPStatus

from flask import Flask, request
from to_do_api.audit_logging.formatter import CustomFormatter
from to_do_api.service.user import UserService
from to_do_api.utils import response_with_status, success_response
from to_do_api.audit_logging import HTTPAuditLogger
import logging

__LOG_FMT = "{\"time\": \"%(asctime)s\", \"name\": \"[%(name)s]\", \"filename\": \"[%(filename)s]\", \"lineno\": \"[%(lineno)s]\", \"levelname\": \"%(levelname)s\", \"message\": \"%(message)s\"}"

application = Flask(__name__)
audit_logger = HTTPAuditLogger.from_env()
audit_logger.start()


logging.basicConfig(level=logging.INFO, format=__LOG_FMT)
root_logger = logging.getLogger()


@application.route("/users", methods=['GET', 'POST'])
@audit_logger.log_inbound(include_request_in_response=False)
def users():
    root_logger.debug(f"{request.path} - {request.method}")
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
    root_logger.info("*** APPLICATION NAME %s", application.name)
    application.run(host="0.0.0.0", port=8000)