#!/usr/bin/env python3
import os
import sys
import pytest
import configparser
from unittest.mock import patch
from PIL import Image

# Append project root to path to ensure clean internal imports
sys.path.insert(0, os.path.abspath(str(os.path.join(str(os.path.dirname(__file__)), ".."))))

from worldmap.tasks.clouds import CloudUpdater
from tests.common import test_env, assert_url_accessible, verify_generated_image


class MockCloudUpdater(CloudUpdater):
    """Subclass of production CloudUpdater for test consistency."""

    def __init__(self, config, map_data):
        super().__init__(config, map_data)


def test_clouds_pipeline(test_env):
    updater = MockCloudUpdater(test_env["config"], test_env["map_data"])

    # 1. Base URL Reachability Assertion
    # Verifying the core host utilized by the CreateCloudMap library
    # Note that this URL is just to provide an indication the provider
    # is still active. It isn't a URL that is used directly by us.
    base_url = updater.settings.get("url", "").strip('"').rstrip("/")
    assert_url_accessible(base_url, "Matteason Clouds Hub")

    def mock_cloudmap_main_execution():
        """Simulates the CreateCloudMap library successfully generating a PNG."""
        # Generate a blank PNG exactly where the temp config told it to
        img = Image.new(
            'RGBA',
            (updater.target_width, updater.target_height),
            color=(255, 255, 255, 0)
        )
        img.save(updater.output_path, "PNG")

    # 2. Pipeline Execution via Context Injection
    with patch("worldmap.tasks.clouds.cloudmap_main", side_effect=mock_cloudmap_main_execution) as mock_main:
        # We explicitly set force=True in the test environment to guarantee execution
        updater.settings["force"] = "True"
        updater.run()

        # Ensure the third-party library was actually called
        mock_main.assert_called_once()

    # 3. Intermediate Config Verification
    # Check that clouds.py correctly generated the intermediate config file for the library
    temp_conf_path = os.path.join(updater.workdir, "data", "cloud_map.conf")
    assert os.path.exists(temp_conf_path), "Temporary cloud_map.conf was not generated!"

    # Parse it to ensure the dimensions and paths match the map_data region
    parser = configparser.ConfigParser()
    parser.read(temp_conf_path)
    assert parser["xplanet"]["width"] == str(test_env["map_data"].region.target_width)
    assert parser["xplanet"]["height"] == str(test_env["map_data"].region.target_height)
    assert parser["xplanet"]["destinationfile"] == os.path.basename(updater.output_path)

    # 4. Structural Image Layout Verification
    assert verify_generated_image(
        updater.output_path,
        test_env["map_data"].region.target_width,
        test_env["map_data"].region.target_height
    )