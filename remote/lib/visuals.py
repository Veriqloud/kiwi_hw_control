import logging

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",     # Cyan
        logging.INFO: "\033[32m",      # Green
        logging.WARNING: "\033[33m",   # Yellow
        logging.ERROR: "\033[31m",     # Red
        logging.CRITICAL: "\033[1;31m" # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)

        original_levelname = record.levelname
        record.levelname = f"{color}{original_levelname}{self.RESET}"
        try:
            return super().format(record)
        finally:
            # IMPORTANT: restore for other handlers (e.g. file logs)
            record.levelname = original_levelname

def mylogger():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter("%(asctime)s %(levelname)s: %(message)s"))

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger





#logger = mylogger()
#
#logger.info("Hello color!")
#logger.error("Something broke")





