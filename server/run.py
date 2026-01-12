"""Custom runner script to ensure proper host binding for Railway."""

import os
import sys

# Set environment variables before any imports
os.environ["PIPECAT_RUNNER_HOST"] = "0.0.0.0"
os.environ["HOST"] = "0.0.0.0"

# Patch uvicorn.run to force host=0.0.0.0
import uvicorn

_original_uvicorn_run = uvicorn.run


def patched_uvicorn_run(app, **kwargs):
    kwargs["host"] = "0.0.0.0"
    kwargs["port"] = int(os.environ.get("PORT", "7860"))
    return _original_uvicorn_run(app, **kwargs)


uvicorn.run = patched_uvicorn_run

if __name__ == "__main__":
    # Set argv for the runner
    sys.argv = ["run.py", "bot:bot"]
    
    from pipecat.runner.run import main
    main()
