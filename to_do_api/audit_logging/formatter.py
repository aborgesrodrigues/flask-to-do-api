import logging

_DEFAULT_LOG_RECORD_KEYS = dir(logging.LogRecord('', 0, '', 0, '', None, None))


class CustomFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super(CustomFormatter, self).__init__(*args, **kwargs)

    def format(self, record):
        if not hasattr(record, self.log_record_name):
            res = {}
            for key, value in record.__dict__.items():
                if key in _DEFAULT_LOG_RECORD_KEYS:
                    continue
                res[key] = value

        return super(CustomFormatter, self).format(record)
