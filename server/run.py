"""Custom runner script to fix Railway host binding.

The pipecat runner's main() ignores --host arguments and binds to localhost.
This script uses pipecat's internal _create_server_app() and runs uvicorn directly
with host="0.0.0.0" to make the server accessible externally.
"""

import os

import uvicorn
from pipecat.runner.run import _create_server_app

if __name__ == "__main__":
    # Create the pipecat app with our bot
    app = _create_server_app("bot:bot")

    # Run uvicorn directly with explicit host binding
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "7860")),
    )
