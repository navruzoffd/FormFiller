import sys
from loguru import logger

file_format = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level: <8} | "
    "{name}:{function}:{line} - {message}"
)

console_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{message}</cyan>"
)

logger.remove()

logger.add("logs/out.log", format=file_format, level="DEBUG")

logger.add(sys.stdout, format=console_format, level="INFO")