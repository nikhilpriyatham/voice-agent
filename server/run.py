"""Custom runner script to ensure proper host binding for Railway."""

import os

# Override the default host BEFORE importing pipecat runner
os.environ["PIPECAT_RUNNER_HOST"] = "0.0.0.0"

import pipecat.runner.run as runner

# Monkey-patch the runner_host to force 0.0.0.0
runner.runner_host = lambda: "0.0.0.0"
runner.RUNNER_HOST = "0.0.0.0"

if __name__ == "__main__":
    runner.main()
