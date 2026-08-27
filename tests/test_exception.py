import sys

from src.agentic.exception import CustomException


def test_custom_exception_captures_traceback_details():
    try:
        raise ValueError("boom")
    except ValueError as e:
        wrapped = CustomException(e, sys)

    message = str(wrapped)
    assert "boom" in message
    assert "test_exception.py" in message
