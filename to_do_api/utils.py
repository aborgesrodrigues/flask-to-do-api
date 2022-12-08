from __future__ import annotations

import typing as t
from http import HTTPStatus

from flask import Response, jsonify, make_response


def success_response(data: t.Union[dict, str]) -> Response:
    return response_with_status(data=data, status=HTTPStatus.OK)


def response_with_status(data: t.Union[dict, str], status: int) -> Response:
    return make_response(jsonify(data), status)
