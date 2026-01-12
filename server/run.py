"""Custom runner script to ensure proper host binding for Railway."""

import os
import sys

# Set host to 0.0.0.0 before importing pipecat runner
os.environ["PIPECAT_RUNNER_HOST"] = "0.0.0.0"
os.environ["PIPECAT_RUNNER_PORT"] = os.environ.get("PORT", "7860")

if __name__ == "__main__":
    # Override sys.argv to include host binding
    sys.argv = [
        "pipecat.runner.run",
        "--host",
        "0.0.0.0",
        "--port",
        os.environ.get("PORT", "7860"),
        "bot:bot",
    ]

    from pipecat.runner.run import main

    main()
