import json
import logging
import os
import queue
import threading
import time
import typing as t
from datetime import datetime
from functools import wraps
from io import BytesIO

import boto3
from botocore.endpoint import is_valid_endpoint_url
from botocore.exceptions import NoCredentialsError
from flask import Request, Response, request

logger = logging.getLogger(__name__)


class Options:
    AUDITLOG_S3_DIRECTORY = "AUDITLOG_S3_DIRECTORY"
    AUDITLOG_S3_REGION = "AUDITLOG_S3_REGION"
    AUDITLOG_S3_BUCKET = "AUDITLOG_S3_BUCKET"
    AUDITLOG_S3_ENDPOINT = "AUDITLOG_S3_ENDPOINT"

    @staticmethod
    def from_env():
        s3_bucket = os.getenv(Options.AUDITLOG_S3_BUCKET, "wcf-audit-local")
        s3_directory = os.getenv(Options.AUDITLOG_S3_DIRECTORY, "todo-api/")
        s3_region = os.getenv(Options.AUDITLOG_S3_REGION, "us-east-1")
        s3_endpoint = os.getenv(Options.AUDITLOG_S3_ENDPOINT, None)
        return Options(s3_bucket=s3_bucket, s3_directory=s3_directory, s3_region=s3_region, s3_endpoint=s3_endpoint)

    def __init__(self, s3_bucket: str, s3_directory: str, s3_region: str,
                 s3_endpoint: str = None):
        self.bucket = s3_bucket
        self.directory = s3_directory
        self.region = s3_region
        self.endpoint = s3_endpoint


class HTTPAuditLogger(threading.Thread):
    """
    This is a concrete Audit record writer that is used to write JSON formatted files to an AWS S3 bucket such that
    they can be consumed by other processes.
    Calls to `log_request` and `log_response` can be called in the main processing thread(s).  The functions are
    thread safe, so multi threads can call the log request/response directly w/o needing to worry about thread issues.
    Internally, this class will marshal the request/response, then use a 2nd thread to do the actual S3 writing.
    This Logger needs to match the GoLang AuditLogger's file naming and file contents.
    """
    _RESERVED_FIELD_NAMES = {
        "identifier", "eventTimestamp", "host", "hostname", "method", "path", "query", "protocol", "headers", "body",
        "requestBody", "requestTimestamp", "requestHost", "requestHostname", "requestMethod", "requestPath",
        "requestProtocol", "status", "statusCode",
    }

    class Record:
        def __init__(self, key: str, content: str):
            self.key = key
            self.content = content

    @staticmethod
    def from_env():
        opts = Options.from_env()
        return HTTPAuditLogger(opts=opts)

    def __init__(self, opts: Options) -> None:
        super(HTTPAuditLogger, self).__init__()

        # validate fields
        if not opts.bucket:
            raise Exception('s3_bucket not informed.')

        if not opts.directory:
            raise Exception('s3_directory not informed.')

        if opts.endpoint:
            if not is_valid_endpoint_url(opts.endpoint):
                raise Exception('s3_endpoint invalid.')

        if not opts.region:
            raise Exception('s3_region not informed.')

        self.s3_bucket = opts.bucket
        self.s3_directory = opts.directory
        self.s3_endpoint = opts.endpoint
        self.s3_region = opts.region

        self.s3_client = boto3.client('s3', region_name=self.s3_region, endpoint_url=self.s3_endpoint)

        self.queue = queue.Queue()
        self.end_event = threading.Event()

    def stop(self):
        self.end_event.set()
        self.join()

    def run(self):
        while not self.end_event.is_set():
            try:
                record = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._do_s3_write(record)

    def log_request(self, req: Request):
        try:
            audit_id = HTTPAuditLogger._make_audit_id(req, False)
            metadata = HTTPAuditLogger._get_request_metadata(req)
            req_data = req
            self._queue_record(audit_id, metadata, req_data)
        except Exception:
            raise

    def log_response(self, req: Request, resp: Response, include_request_in_response: bool,
                     request_timestamp: t.Optional[datetime]):
        try:
            audit_id = HTTPAuditLogger._make_audit_id(req, True)
            metadata = HTTPAuditLogger._get_response_metadata(req, resp, include_request_in_response, request_timestamp)
            req_data = req
            self._queue_record(audit_id, metadata, req_data)
        except Exception:
            raise

    def _queue_record(self, audit_id: str, data: dict, req_data: t.Optional[Request]):
        # Set the identifier and Timestamp last to ensure it's not overridden.
        # To help consistency, these two fields are set in the golang `audit/logger.go` file, while the `data`
        # fields are populated in the `httpaudit/httpaudit.go` file.
        data["eventTimestamp"] = _utc_now_str()
        data["identifier"] = audit_id

        record = HTTPAuditLogger.Record(
            key=self._make_key(audit_id),
            content=json.dumps(data)
        )
        self.queue.put(record, block=False)

    def _do_s3_write(self, record: Record) -> None:
        """
        Save content to s3 bucket, should not be called in main thread
        """
        metadata = {}       # The metadata parameter can't be None or Boto3 raises an error
        try:
            s3_put_response = self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=record.key,
                Body=record.content,
                ContentEncoding="binary/octet-stream",
                ContentType="application/json; charset=utf-8",
                ContentLength=len(record.content),
                ServerSideEncryption="AES256",
                Metadata=metadata
            )

            if s3_put_response['ResponseMetadata']['HTTPStatusCode'] != 200:
                raise Exception(f'Unable to put data to s3: {s3_put_response}')

            return_object = {
                "region": self.s3_region,
                "location": f's3://{self.s3_bucket}/{record.key}'
            }
            logger.info(f"Wrote audit log. {return_object}")

        except NoCredentialsError as err:
            logger.error(f"Error writing audit log. {str(err)}")
        except Exception as err:
            logger.error(f"Error writing audit log. {str(err)}")

    def _make_key(self, audit_id: str) -> str:
        key = f'{self.s3_directory}/{datetime.now().strftime("%Y/%m/%d/%H/")}{audit_id}'
        return key

    @staticmethod
    def _get_request_metadata(req: Request) -> dict:
        metadata = {
            "host": req.host,
            "hostname": req.root_url,
            "method": req.method,
            "path": req.path,
            "protocol": req.environ.get('SERVER_PROTOCOL'),
            "query": req.query_string.decode("utf-8"),  # convert to string
            "headers": list(req.headers),
        }

        if req.content_length:
            metadata["body"] = HTTPAuditLogger._request_body(req)

        return metadata

    @staticmethod
    def _get_response_metadata(req: Request, response: Response, include_request_in_response: bool,
                               request_timestamp: t.Optional[str]) -> dict:
        metadata = {
            "requestHost": req.host,
            "requestHostname": req.root_url,
            "requestMethod": req.method,
            "requestPath": req.path,
            "requestProtocol": req.environ.get('SERVER_PROTOCOL'),
            "protocol": req.environ.get('SERVER_PROTOCOL'),
            "status": response.status,
            "statusCode": response.status_code,
            "headers": list(response.headers),
        }
        if response.content_length:
            metadata["body"] = HTTPAuditLogger._response_body(resp=response)

        if include_request_in_response:
            if req.content_length:
                metadata["requestBody"] = HTTPAuditLogger._request_body(req)
            if request_timestamp:
                metadata["requestTimestamp"] = request_timestamp

        return metadata

    @staticmethod
    def _make_audit_id(req: Request, is_response: bool) -> str:
        """
        Creates an audit id for an `upstream` audit log record.  See golang package for more details
        The Audit ID should be unique, so for an HTTP message we append the nanosecond timestamp to the end
        """
        audit_id = "in{0}{1}{2}{3}".format(req.path, "" if req.path.endswith("/") else "/", req.method,
                                           "/response" if is_response else "/request")
        audit_id += f'_{time.time_ns()}'
        return audit_id

    @staticmethod
    def _request_body(req: Request) -> str:
        """
        Retrieve the request body without making it unavailable
        consuming the form data in middleware will make it unavailable to the final application
        """
        body = req.data
        # noinspection PyBroadException
        try:
            req.environ['wsgi.input'] = BytesIO(body)
            content = body.decode("utf-8")
            # Try to convert to Python object.  If fails, return as byte array
            try:
                json_body = json.loads(content)
                return json_body
            except ValueError:
                pass

        except Exception:
            content = "bodyReadError"
        return content

    @staticmethod
    def _response_body(resp: Response) -> str:
        """
        Retrieve the response body without making it unavailable
        """
        body = resp.data
        # noinspection PyBroadException
        try:
            content = body.decode("utf-8")
            # Try to convert to Python object.  If fails, return as byte array
            try:
                json_body = json.loads(content)
                return json_body
            except ValueError:
                pass
        except Exception:
            content = "bodyReadError"
        return content

    # Decorators for direct use of this Audit Logger class
    def log_inbound(self, log_request=True, log_response=True,
                    include_request_in_response=False):
        """
        Usage 1: add audit logging to route and log both inbound and outbound messages
        .. code-block:: python
        @app.route("/some_route")
        @audit_logger.log_inbound()
        def handle_request():
            do work...

        Usage 2: Only log the request, not the response
        .. code-block:: python
        @app.route("/some_route")
        @audit_logger.log_inbound(log_response=False)
        def handle_request():
            do work...

        :param log_request: Generate Request Audit Log message
        :param log_response: Generate Response Audit Log message
        :param include_request_in_response:  If True, adds the request body as top level field in response audit log
        """

        def _log_inbound(f):
            @wraps(f)
            def __log_inbound(*args, **kwargs):
                request_timestamp = None
                if include_request_in_response:
                    request_timestamp = _utc_now_str()
                if log_request:
                    self.log_request(req=request)
                result = f(*args, **kwargs)
                if log_response:
                    self.log_response(req=request, resp=result, include_request_in_response=include_request_in_response,
                                      request_timestamp=request_timestamp)
                return result

            return __log_inbound

        return _log_inbound


def _utc_now_str() -> str:
    """
    Not the ideal way to do ISO timestamp formatting to add UTC 'Z' to the end,
    We are passing in UTC time, but not setting a timezone, so this is a quick solution
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    return timestamp
