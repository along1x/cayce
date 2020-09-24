import logging
import os
import sys
import tempfile
from typing import Optional


_logger_by_name = {}


def get_logger(
    name: str,
    console_level: int = logging.INFO,
    file_level: Optional[int] = None,
    log_dir: Optional[str] = None,
    log_file_name: Optional[str] = None,
) -> logging.Logger:
    """
    Configure and return a logger

    Args:
        name (str): Name of the logger
        console_level (int, optional):
            Message level that will be printed to stdout.
            Use constants DEBUG, INFO, WARNING, CRITICAL from logging.
            Use None to turn off console logging.
            Defaults to INFO.
        file_level (int, optional):
            Message level that will be printed to a file.
            Use constants DEBUG, INFO, WARNING, CRITICAL from logging.
            Use None to turn off file logging.
            Defaults to None.
        log_dir (str, optional):
            Location of log files.  Defaults to %TEMP%/logs.
        log_file_name (str, optional):
             Name of the log file.
             Defaults to the command line arguments for the application.

    Returns:
        [Logger]: A configured logger instance
    """
    if name in _logger_by_name:
        return _logger_by_name[name]

    logger = logging.getLogger(name)

    # if a log name was provided without a directory, provide a default
    if log_file_name and not log_dir:
        log_dir = os.path.join(tempfile.gettempdir(), "edgar", "logs")

    if log_dir and not os.path.exists(log_dir):
        os.mkdir(log_dir)

    log_format = "%(asctime)s : %(module)s.%(funcName)s : %(levelname)s : %(message)s"
    formatter = logging.Formatter(log_format)

    # Set up logging to the console
    if console_level:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level=console_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Set up logging to a file
    if file_level and log_dir:
        executable = os.path.basename(sys.argv[0])
        args = sys.argv[1:]
        default_file_name = f'{executable}{"-".join(args) if args else ""}.log'
        log_file_name = log_file_name if log_file_name else default_file_name

        file_handler = logging.FileHandler(os.path.join(log_dir, log_file_name))
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Select the least restrictive logging level
    console_level = console_level if console_level else logging.CRITICAL
    file_level = file_level if file_level else logging.CRITICAL
    logger.setLevel(min(console_level, file_level))

    _logger_by_name[name] = logger

    return logger
