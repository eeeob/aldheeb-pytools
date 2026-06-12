from typing import Optional, Union, IO, Callable
from pathlib import Path

from dataclasses import dataclass
from logging import (
    getLogger, Formatter, 
    LogRecord, Logger, 
    Handler, FileHandler, StreamHandler, 
)

from ..errors import ValidationError

@dataclass(slots=True, kw_only=True)
class _LoggerModel:
    logger: Optional[Union[Logger, str]] = None

    level: Optional[int] = None
    filter: Optional[Callable[[LogRecord], bool]] = None

    def resolve_logger(self) -> Logger:
        logger = self.logger

        if logger is None or isinstance(logger, str):
            self.logger = getLogger(logger)
        elif not isinstance(logger, Logger):
            raise ValidationError("Invalid Logger %s" % str(logger))
        
        return self.logger
    
@dataclass(slots=True, kw_only=True)
class LogHandlerOptions(_LoggerModel):
    handler: Union[Handler, IO, Path, str]
    formatter: Optional[Formatter] = None

    def resolve_handler(self) -> Union[FileHandler, StreamHandler]:
        hdlr = self.handler

        if isinstance(hdlr, (Path, str)):
            self.handler = FileHandler(hdlr, encoding="utf-8")
        elif isinstance(hdlr, IO):
            self.handler = StreamHandler(hdlr)
        elif not isinstance(hdlr, Handler):
            raise ValidationError("Invalid Logger Handler %s" % str(hdlr))
        
        return self.handler

@dataclass(slots=True, kw_only=True)
class LoggerOptions(_LoggerModel):
    propagate: Optional[bool] = None
    reset_level: Optional[bool] = None




__all__ = (
    "LogHandlerOptions", 
    "LoggerOptions", 
)