#!/usr/bin/env python3
import os
import sys
import json
import logging
import asyncio
import websockets
from worldmap.lib.config import WorldMapConfig
from worldmap.lib.shipping import ShipCache

logger = logging.getLogger(__name__)


class ShipHarvester:
    settings = None
    ship_database = None

    def __init__(self, config_path):
        self.config = WorldMapConfig(config_path)
        self.workdir = self.config.get_section("common").get("workdir", ".")
        logger.info(f"Workdir: {self.workdir} Now getting settings")
        self.load_settings()

    def load_settings(self):
        self.config.load()
        self.settings = self.config.get_section("shipping_harvester")
        db_rel = self.settings.get("static_database")
        self.ship_database = str(os.path.join(self.workdir, db_rel))

    async def run(self):
        # Refresh settings immediately before starting harvest
        self.load_settings()

        url = self.settings.get("url")
        api_key = self.settings.get("api_key")
        bbox = json.loads(self.settings.get("bbox"))
        listen_duration = self.settings.getint("listen_for_static_data", fallback=300)

        # Initialize the shared cache library
        cache = ShipCache(self.ship_database)
        initial_count = len(cache.data)
        logger.info(f"Initial ship count: {initial_count}")

        sub = {
            "APIKey": api_key,
            "BoundingBoxes": bbox,
            "FilterMessageTypes": ["ShipStaticData"],
        }

        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(sub))
                start_time = asyncio.get_event_loop().time()

                logger.info(f"Harvesting ship static data for {listen_duration}s")
                while asyncio.get_event_loop().time() - start_time < listen_duration:
                    try:
                        msg_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        msg = json.loads(msg_raw)

                        if msg.get("MessageType") == "ShipStaticData":
                            m = msg.get("MetaData", {})
                            b = msg.get("Message", {}).get("ShipStaticData", {})
                            mmsi = str(m.get("MMSI") or b.get("UserID", ""))
                            if mmsi:
                                cache.update_from_static(mmsi, m, b)

                    except asyncio.TimeoutError:
                        continue

            # Save the updated cache back to disk
            cache.save()
            logger.info(
                f"Harvest complete. Total records: {len(cache.data)} (+{len(cache.data) - initial_count})"
            )
        except Exception as e:
            logger.error(f"Harvester connection error: {e}")
            sys.exit(1)


def main():
    import argparse
    from worldmap.lib.logging import setup_logging

    setup_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    harvester = ShipHarvester(args.config)
    asyncio.run(harvester.run())


if __name__ == "__main__":
    main()
