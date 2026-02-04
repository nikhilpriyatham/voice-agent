"""
bot_runner.py

HTTP service that creates Daily rooms and starts the Pipecat bot.
This handles the WebRTC infrastructure through Daily.co, solving NAT traversal issues.
"""

import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pipecat.transports.services.helpers.daily_rest import (
    DailyRESTHelper,
    DailyRoomParams,
    DailyRoomProperties,
)
from utils.payer_singleton import get_payer_lookup  # Pre-load payer database

load_dotenv(override=True)

# Pre-load payer lookup at server startup (saves 1-2s per call)
logger.info("Initializing payer lookup singleton at startup...")
try:
    get_payer_lookup()
    logger.info("Payer lookup singleton loaded successfully")
except Exception as e:
    logger.error(f"Failed to pre-load payer lookup: {e}")

# Configuration
MAX_SESSION_TIME = 10 * 60  # 10 minutes

daily_helpers = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Daily REST helper on startup."""
    aiohttp_session = aiohttp.ClientSession()
    daily_helpers["rest"] = DailyRESTHelper(
        daily_api_key=os.getenv("DAILY_API_KEY", ""),
        daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
        aiohttp_session=aiohttp_session,
    )
    yield
    await aiohttp_session.close()


app = FastAPI(lifespan=lifespan)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def launch_bot(room_url: str, token: str, patient_name: str, device_ordered: str):
    """Launch the bot as a subprocess to join the Daily room."""
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bot_script = os.path.join(script_dir, "bot_daily.py")

        # Launch the bot subprocess
        subprocess.Popen(
            [
                sys.executable,
                bot_script,
                "--room-url",
                room_url,
                "--token",
                token,
                "--patient-name",
                patient_name,
                "--device-ordered",
                device_ordered,
            ],
            env=os.environ.copy(),
            cwd=script_dir,
        )
        logger.info(f"Bot launched for room: {room_url}")
    except Exception as e:
        logger.error(f"Failed to launch bot: {e}")
        raise


@app.post("/api/connect")
async def connect(request: Request) -> JSONResponse:
    """
    Create a Daily room, launch the bot, and return connection details.
    The client will connect to this room using Daily's WebRTC infrastructure.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}

    # Extract patient info from request
    patient_name = data.get("patient_name", os.getenv("PATIENT_NAME", "the patient"))
    device_ordered = data.get(
        "device_ordered", os.getenv("DEVICE_ORDERED", "medical equipment")
    )

    logger.info(f"Creating room for patient: {patient_name}, device: {device_ordered}")

    try:
        # Create a Daily room
        room = await daily_helpers["rest"].create_room(
            DailyRoomParams(
                properties=DailyRoomProperties(
                    exp=int(time.time()) + MAX_SESSION_TIME,
                    enable_chat=False,
                    enable_emoji_reactions=False,
                    enable_hand_raising=False,
                    start_video_off=True,
                )
            )
        )

        # Get a token for the user to join
        token = await daily_helpers["rest"].get_token(room.url, MAX_SESSION_TIME)

        # Get a token for the bot
        bot_token = await daily_helpers["rest"].get_token(room.url, MAX_SESSION_TIME)

        logger.info(f"Room created: {room.url}")

        # Launch the bot to join this room
        launch_bot(room.url, bot_token, patient_name, device_ordered)

        # Return room credentials to the client
        return JSONResponse(
            {
                "room_url": room.url,
                "token": token,
            }
        )

    except Exception as e:
        logger.error(f"Failed to create room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # Check for required environment variables
    if not os.getenv("DAILY_API_KEY"):
        raise Exception("Missing DAILY_API_KEY environment variable")

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 7860))

    logger.info(f"Starting bot runner on {host}:{port}")
    uvicorn.run("bot_runner:app", host=host, port=port, reload=False)
