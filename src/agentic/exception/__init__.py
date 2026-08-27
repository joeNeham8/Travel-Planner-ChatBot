import sys


def error_message_detail(error: Exception, error_detail) -> str:
    """
    Build a detailed error string including file name and line number.
    `error_detail` should be the `sys` module (so we can call sys.exc_info()).
    """
    _, _, exc_tb = error_detail.exc_info()

    if exc_tb is not None:
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno
    else:
        # Raised outside an active except block — no traceback available.
        file_name = "<unknown>"
        line_number = -1

    return "Error occurred in python script [{0}] line number [{1}] error message [{2}]".format(
        file_name, line_number, str(error)
    )


class CustomException(Exception):
    """
    Usage (inside an `except` block, so traceback info is available):

        try:
            ...
        except Exception as e:
            raise CustomException(e, sys) from e

    NOTE: argument order is (error, error_detail) — i.e. the exception first,
    then the `sys` module. This matches how every raise site in this project
    calls it; the original version had the order swapped, which crashed the
    error handler itself.
    """

    def __init__(self, error: Exception, error_detail=sys):
        super().__init__(str(error))
        self.error_message = error_message_detail(error, error_detail=error_detail)

    def __str__(self):
        return self.error_message
