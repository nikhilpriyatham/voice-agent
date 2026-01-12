"""Custom runner script to fix Railway host binding.

Exposes the pipecat app for uvicorn CLI to run with explicit host binding.
"""

from pipecat.runner.run import _create_server_app

# Create the app at module level so uvicorn can import it
app = _create_server_app("bot:bot")
