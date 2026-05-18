#!/usr/bin/env python3
import os
import configparser
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="WorldMap Configuration API")

# Setup CORS so your browser running on port 8080 can talk to port 8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Fine for local dev tweaking
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = "/opt/project/config/worldmap.conf"


# Strictly map out what we expect from the UI input
class ConfigUpdate(BaseModel):
    url: str
    step: float
    bbox: list[float]


def load_raw_config():
    """Helper to cleanly parse the live configuration file."""
    if not os.path.exists(CONFIG_PATH):
        raise HTTPException(status_code=404, detail=f"Config file not found at {CONFIG_PATH}")

    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config


@app.get("/api/config")
def get_config():
    """Reads worldmap.conf and pulls settings out for the UI."""
    config = load_raw_config()

    # Safely unpack your configuration sections with smart local fallbacks
    precipitation_url = config.get("precipitation", "url",
                                   fallback="https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod")
    step_size = config.getfloat("precipitation", "step", fallback=0.02)

    # Parse the bounding box array out of its string format
    bbox_str = config.get("region", "bbox", fallback="156.0,-22.0,164.0,-14.0")
    try:
        bbox_list = [float(x.strip()) for x in bbox_str.split(",")]
    except ValueError:
        bbox_list = [156.0, -22.0, 164.0, -14.0]

    return {
        "status": "success",
        "data": {
            "url": precipitation_url,
            "step": step_size,
            "bbox": bbox_list
        }
    }


@app.post("/api/config")
def update_config(payload: ConfigUpdate):
    """Mutates the live .conf file with user inputs from the UI dashboard."""
    config = load_raw_config()

    # Ensure sections exist before updating them
    if not config.has_section("precipitation"):
        config.add_section("precipitation")
    if not config.has_section("region"):
        config.add_section("region")

    # Inject the fresh values back into the structural blocks
    config.set("precipitation", "url", payload.url)
    config.set("precipitation", "step", str(payload.step))

    # Flatten the bounding box float array back into a comma-separated string
    bbox_string = ",".join(str(val) for val in payload.bbox)
    config.set("region", "bbox", bbox_string)

    # Flush the updates directly back to disk
    try:
        with open(CONFIG_PATH, "w") as config_file:
            config.write(config_file)
        return {"status": "success", "message": "Configuration updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write configuration to file: {str(e)}")
