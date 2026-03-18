import sys
import os

# Ensure ai_advisory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ai_advisory.config
# Force LLM off for all tests
ai_advisory.config.USE_LLM = False
