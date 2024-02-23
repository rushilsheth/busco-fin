# Import and configure logging 
import logging
import sys
def get_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create a handler to log to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    return logger