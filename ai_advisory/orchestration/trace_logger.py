import os
import logging

def reset_trace():
    logging.info("--- NEW SIMULATION RUN ---")

def trace_log(*args, **kwargs):
    msg = " ".join(str(arg) for arg in args)
    logging.info(msg)
