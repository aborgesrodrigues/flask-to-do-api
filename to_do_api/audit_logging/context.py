from __future__ import annotations

import inspect
import json
import logging
import os.path
import typing as t

from flask import Request, Response, request

logger = logging.getLogger(__name__)


class RequestContext:
    """
    This class is used to access the Extra Context added by the GPCL.
    Specifically it adds the ability to get the common Header Fields used in out services
    """

    def __init__(self) -> t.Optional[RequestContext]:
        self._internal = Context.from_request()
        if self._internal is None:
            raise Exception("RequestContext called before request was processed by application handlers.")

    @property
    def correlation_id(self) -> str:
        """
        Returns the Correlation ID, if extracted from the Request Header
        @return:
        """
        return self._internal.correlation_id

    @property
    def instruction_set(self) -> str:
        """
        Returns the Instruction Set, if extracted from the Request Header
        @return:
        """
        return self._internal.instruction_set


class RouteContext:
    """
    This class is used to access extra context supported per Route call.
    Anything added/changed via this class is only applicable for the single Route it's a part of.
    """

    def __init__(self) -> t.Optional[RouteContext]:
        self._internal = Context.from_request()
        if self._internal is None:
            raise Exception("RouteContext called before request was processed by application handlers.")

    @property
    def correlation_id(self) -> str:
        """
        Returns the Correlation ID, if extracted from the Request Header
        @return:
        """
        return self._internal.correlation_id

    @property
    def instruction_set(self) -> str:
        """
        Returns the Instruction Set, if extracted from the Request Header
        @return:
        """
        return self._internal.instruction_set

    def add_log_field(self, key: str, value: t.Union[str, dict]) -> None:
        """
        This function will add a top level field to both the Elasticsearch Logged message and the Audit Logger.
        @param key: Top Level Name in the Audit Log
        @param value: Content of the data
        @return: None
        """
        self._internal.add_log_field(key=key, value=value)

    def add_audit_log_response_field(self, key: str, value: t.Union[str, dict]) -> None:
        """
        This function will add a field ONLY to the Audit Log.  This should be used when we have large data we
        want to store off, or data that contains PII that we don't need to log.
        @param key: Top Level Name in the Audit Log
        @param value: Content of the data
        @return: None
        """
        self._internal.add_audit_log_response_field(key=key, value=value)


class Context:
    """
    This is an internal class which handles all the actual request/response interaction that happens
    within the context of a Request.
    It's purposefully separate from the exposed RequestContext and RouteContext classes, as we want to limit the
    ability of users of the library to get at the internals of this class
    """
    # HTTP Header Keys
    __CORRELATION_ID_KEY = "Correlation-Id"
    __INSTRUCTION_SET_KEY = "x-gradient-instruction-set"
    __LOGGED_FIELDS_KEY = "K-Logged-Fields"

    # Audit Logger Top level Key names:
    _CORRELATION_ID_LOG_KEY = "correlationId"
    _INSTRUCTION_SET_LOG_KEY = "instructionSet"

    __REQUEST_ATTRIBUTE_NAME = "gpcl"

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
            return getattr(req, Context.__REQUEST_ATTRIBUTE_NAME, None)
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

        self.correlation_id = Context._get_header_value(req, Context.__CORRELATION_ID_KEY)
        if self.correlation_id is None:
            # TODO:  Generate value like golang: correlationID = xid.New().String()
            # possibly use: https://github.com/scys/python_xid
            logger.debug(f'No {Context.__CORRELATION_ID_KEY} header found.')

        self.instruction_set = Context._get_header_value(req, Context.__INSTRUCTION_SET_KEY)
        if self.instruction_set is None:
            logger.debug(f'No {Context.__INSTRUCTION_SET_KEY} header found.')

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
        delattr(self.req, Context.__REQUEST_ATTRIBUTE_NAME)
        self.req = None

    def set_in_request(self, req: Request) -> Context:
        setattr(req, Context.__REQUEST_ATTRIBUTE_NAME, self)
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

        if self.correlation_id:
            extra[Context._CORRELATION_ID_LOG_KEY] = self.correlation_id

        if self.instruction_set:
            extra[Context._INSTRUCTION_SET_LOG_KEY] = str(self.instruction_set)

        if self._logged_fields:
            extra.update(self._logged_fields)

        return extra

    def get_audit_log_top_level_fields(self) -> t.Dict[str, t.Any]:
        fields = self.get_logger_top_level_fields()
        fields.update(self._audit_log_only_fields)
        return fields

    def add_response_headers(self, resp: Response) -> None:
        if self.correlation_id:
            resp.headers[Context.__CORRELATION_ID_KEY] = self.correlation_id
        if self.instruction_set:
            resp.headers[Context.__INSTRUCTION_SET_KEY] = self.instruction_set
        if self._raw_logged_fields:
            resp.headers[Context.__LOGGED_FIELDS_KEY] = self._raw_logged_fields

    @staticmethod
    def _get_header_value(req: request, key: str, default: t.Optional[str] = None) -> t.Optional[t.Any]:
        val = req.headers.get(key, default)
        if val is None:
            return None
        return val.strip()
