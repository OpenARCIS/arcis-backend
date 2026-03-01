import os
import logging
import inspect
from pathlib import Path

log_file_path = "./arcis/logs/arcis.log"

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("/webdav") == -1


class Logger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
            
        logging.getLogger("pyrogram").setLevel(logging.WARNING)

        # prevent propagation to root logger to avoid duplicates
        self.logger.propagate = False

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        file_handler = logging.FileHandler(log_file_path, 'a', 'utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Less verbose for console
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _get_caller_info(self):
        """Get caller filename and line number"""
        caller_frame = inspect.currentframe().f_back.f_back
        caller_filename = os.path.basename(caller_frame.f_globals['__file__'])
        caller_lineno = caller_frame.f_lineno
        return caller_filename, caller_lineno

    def debug(self, message):
        caller_filename, caller_lineno = self._get_caller_info()
        self.logger.debug(f'{caller_filename}:{caller_lineno} - {message}')

    def info(self, message):
        self.logger.info(f'{message}')

    def warning(self, message):
        self.logger.warning(f'{message}')

    def error(self, message, exc_info=False):
        caller_filename, caller_lineno = self._get_caller_info()
        self.logger.error(f'{caller_filename}:{caller_lineno} - {message}', exc_info=exc_info)

    def critical(self, message):
        caller_filename, caller_lineno = self._get_caller_info()
        self.logger.critical(f'{caller_filename}:{caller_lineno} - {message}')


LOGGER = Logger()