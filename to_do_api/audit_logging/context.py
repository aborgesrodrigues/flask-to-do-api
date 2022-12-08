from __future__ import annotations

import inspect
import json
import logging
import os.path
import typing as t

from flask import Request, Response, request

logger = logging.getLogger(__name__)


class Context:
    """
    This is an internal class which handles all the actual request/response interaction that happens
    within the context of a Request.
    It's purposefully separate from the exposed RequestContext and RouteContext classes, as we want to limit the
    ability of users of the library to get at the internals of this class
    """
    # HTTP Header Keys
    __LOGGED_FIELDS_KEY = "K-Logged-Fields"

    @staticmethod
    def from_request(req: t.Optional[Request] = None, silence_outside_context: bool = False) -> t.Optional[Context]:
        """
        Get the Context object from the Flask Request class.  This will always return the same Context class
        per HTTP request.
        This function will return None if the Context object doesn't exist yet, or this function is called in a separate
        thread from the context thread.
        @param req: Flask request (Optional)
        @param silence_outside_context: If set to True, don't increment/warn that this call is happening outside
                the request context.
        @return: Context object or None
        """
        try:
            if req is None:
                req = request
            return None
        except RuntimeError as err:
            if 'Working outside of request context' not in str(err):
                raise
            if not silence_outside_context:
                function_name = "GPCL_Context_from_request"
                # Try to grab the calling function name, if possible
                try:
                    prev_code = inspect.currentframe().f_back.f_code
                    function_name = prev_code.co_name
                    filename = os.path.basename(prev_code.co_filename)
                    logger.debug("Attempted to get Context outside of Request processing.  %s[%s:%s]",
                                 function_name, filename, prev_code.co_firstlineno)
                except Exception as inspect_err:
                    logger.debug("Attempted to get Context outside of Request processing.  Unable to get callstack: %s",
                                 str(inspect_err))
  
        return None

    def __init__(self, req: Request) -> None:
        self.req = None
        self._logged_fields = {}
        self._audit_log_only_fields = {}

        self._raw_logged_fields = Context._get_header_value(req, Context.__LOGGED_FIELDS_KEY)
        if self._raw_logged_fields:
            # convert logged field to dict
            try:
                self._logged_fields = json.loads(self._raw_logged_fields)

                # if is not a dict logs an error
                if not isinstance(self._logged_fields, dict):
                    logger.error(f"Invalid {Context.__LOGGED_FIELDS_KEY} header value: "
                                 f"type {type(self._logged_fields)}")
                    self._logged_fields = {}

            except json.JSONDecodeError as e:
                logger.error(f"Invalid {Context.__LOGGED_FIELDS_KEY} header value: {e}")

    def __enter__(self) -> Context:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.req = None

    def set_in_request(self, req: Request) -> Context:
        self.req = req
        return self

    def add_log_field(self, key: str, value: t.Union[str, dict]) -> None:
        # If this is a list/dict try to convert it to json string
        if isinstance(value, (list, tuple, dict)):
            value = json.dumps(value)

        self._logged_fields[key] = value

    def add_audit_log_response_field(self, key: str, value: t.Union[str, dict]) -> None:
        # Store Audit Log fields natively.  Caller should ensure that the value can be JSON encoded
        self._audit_log_only_fields[key] = value

    def get_logger_top_level_fields(self) -> t.Dict[str, t.Any]:
        """
        This function should return a dictionary of strings, where the Key is the Top Level field name
        and the value is the data to send.
        """
        extra = {}

        if self._logged_fields:
            extra.update(self._logged_fields)

        return extra

    def get_audit_log_top_level_fields(self) -> t.Dict[str, t.Any]:
        fields = self.get_logger_top_level_fields()
        fields.update(self._audit_log_only_fields)
        return fields

    def add_response_headers(self, resp: Response) -> None:
        if self._raw_logged_fields:
            resp.headers[Context.__LOGGED_FIELDS_KEY] = self._raw_logged_fields

    @staticmethod
    def _get_header_value(req: request, key: str, default: t.Optional[str] = None) -> t.Optional[t.Any]:
        val = req.headers.get(key, default)
        if val is None:
            return None
        return val.strip()
