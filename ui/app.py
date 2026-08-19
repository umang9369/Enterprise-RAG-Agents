import os
import time
import uuid

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables explicitly from the root directory
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)

# Initialize Logfire
LOGFIRE_STATUS = "Unknown"
try:
    token = os.getenv("LOGFIRE_TOKEN")
    base_url = os.getenv("LOGFIRE_BASE_URL")
    # EU Logfire v2 tokens must hit the EU endpoint.
    if not base_url and token and token.startswith("pylf_v2_eu_"):
        base_url = "https://logfire-eu.pydantic.dev"
    if not token:
        print("ERROR: LOGFIRE_TOKEN is empty or None!")
        LOGFIRE_STATUS = "Standby (LOGFIRE_TOKEN not set)"
    else:
        logfire.configure(
            token=token,
            advanced=logfire.AdvancedOptions(base_url=base_url) if base_url else None,
        )
        LOGFIRE_STATUS = "Connected & Tracing"
except Exception as e:
    print(f"Logfire Init Error in UI: {e}")
    LOGFIRE_STATUS = f"Standby (Error: {e})"


