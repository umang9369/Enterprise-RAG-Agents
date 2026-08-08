import json
import os
import sys
import uuid


# logfire must be configured before app module imports so spans from
# chunking/loaders/embedding are captured from the start.