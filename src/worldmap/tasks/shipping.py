#!/usr/bin/env python3
import os
import json
import logging
import asyncio
import websockets
from websockets.exceptions import ConnectionClosed

# Internal library imports
from worldmap.lib.config import WorldMapConfig
from worldmap.lib.shipping import ShipCache, get_vessel_class, get_vessel_subclass

logger = logging.getLogger(__name__)


class ShippingUpdater:
    def __init__(self, config: WorldMapConfig):
        self.config = config
        self.settings = config.get_section("shipping")
        self.common = config.get_section("common")
        self.workdir = self.common.get("workdir", ".")

        # Path resolution
        db_rel = config.get_section("shipping_harvester").get("static_database")
        self.full_db_path = os.path.join(self.workdir, db_rel)
        self.output_path = os.path.join(self.workdir, self.settings.get("outfile"))

    async def _get_ais_stream(self, url, subscription, duration):
        """Internal helper for websocket streaming."""
        messages = []
        try:
            async with websockets.connect(url, close_timeout=1) as ws:
                await ws.send(json.dumps(subscription))
                start = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start < duration:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        messages.append(json.loads(msg))
                    except asyncio.TimeoutError:
                        continue
                    except ConnectionClosed:
                        break
        except Exception as e:
            if "no close frame" not in str(e):
                logger.error(f"WebSocket failure: {e}")
        return messages

    async def run(self):
        # Ensure the task is enabled
        if not self.settings.getboolean("enabled", fallback=False):
            logger.info("Shipping task disabled. Skipping.")
            # Truncate existing markers to avoid stale data on map
            with open(self.output_path, "w") as _:
                pass
            return

        api_key = self.settings.get("api_key")
        url = self.settings.get("url")
        bbox = json.loads(self.settings.get("bbox"))

        # Initialize Shared Cache Library
        ship_cache = ShipCache(self.full_db_path)
        selected_ships = {}

        # --- Phase 1: Positions ---
        logger.info(
            f"Streaming AIS positions for {self.settings.get('listen_for_positional_data')}s..."
        )
        pos_sub = {
            "APIKey": api_key,
            "BoundingBoxes": bbox,
            "FilterMessageTypes": ["PositionReport"],
        }
        raw_pos = await self._get_ais_stream(
            url, pos_sub, self.settings.getint("listen_for_positional_data")
        )

        show_only_active = self.settings.getboolean("filter_only_active_ships", fallback=False)
        show_ship_classes = json.loads(
            self.settings.get("filter_show_ship_classes", fallback='["Tanker", "Cargo"]')
        )

        for msg in raw_pos:
            if msg.get("MessageType") != "PositionReport":
                continue

            meta = msg.get("MetaData", {})
            m_data = msg.get("Message", {}).get("PositionReport", {})
            mmsi = str(meta.get("MMSI", ""))

            sog = m_data.get("Sog", 0.0)
            status = m_data.get("NavigationalStatus", 15)

            # Filter for active ships if requested
            # NB: sog is speed in knots, status is anchored or moored
            if show_only_active is False or (sog > 1.0 and status not in [1, 5]):
                cached = ship_cache.data.get(mmsi, {})
                ship_type_code = cached.get("type", 0)
                ship_class = get_vessel_class(ship_type_code)

                # Show this ship if no filtering is set, otherwise the vessel
                # class must be in the list
                if len(show_ship_classes) == 0 or ship_class in show_ship_classes:
                    selected_ships[mmsi] = {
                        "lat": meta.get("latitude"),
                        "lon": meta.get("longitude"),
                        "name": (cached.get("name") or meta.get("ShipName", "Unknown")).strip(),
                        "type": cached.get("type", 0),
                        "sog": sog,
                        "length": cached.get("length", 0),
                        "beam": cached.get("beam", 0),
                        "draught": cached.get("draught", 0.0),
                        "prev_draught": cached.get("prev_draught", 0.0),
                    }

        # --- Phase 3: Write Xplanet Markers ---
        label_color = self.settings.get("marker_color", fallback="red")
        show_ship_classes = json.loads(
            self.settings.get("filter_show_names_for_classes", fallback='["Tanker"]')
        )
        base_label_fontsize = float(self.settings.get("label_fontsize", fallback="12"))

        with (open(self.output_path, "w") as f):
            for mmsi, info in selected_ships.items():
                ship_length, ship_beam = int(info["length"]), int(info["beam"])
                if ship_length < int(self.settings.get("filter_ships_minimum_length", 0)):
                    continue

                # Ship info
                ship_type_code = info["type"]
                ship_latitude = info["lat"]
                ship_longitude = info["lon"]

                # Get the basic type stripped of suffixes
                ship_class = get_vessel_class(ship_type_code)
                ship_subclass = get_vessel_subclass(ship_type_code)

                # Select Symbol based on draught change (Loading/Unloading)
                suffix = (
                    "_empty.png"
                    if (0 < info["draught"] < info["prev_draught"] > 0)
                    else ".png"
                )
                if ship_class == "Tanker":
                    prefix = "ship_tanker"
                elif ship_class == "Cargo":
                    prefix = "ship_cargo"
                else:
                    prefix = "ship"
                    suffix = ".png"
                ship_symbol = f"{prefix}{suffix}"

                if ship_class in show_ship_classes:

                    # Text size for Tankers may be scaled based on dimensions
                    label_suffix = ""
                    if ship_class == "Tanker":
                        if ship_length > 350 or ship_beam > 60:
                            label_size = int(base_label_fontsize * 2.0)  # Ultra
                            label_suffix = " [ULTRA]"
                        elif ship_length > 250:
                            label_size = int(base_label_fontsize * 1.6)  # VLCC
                            label_suffix = " [VLCC]"
                            label_color = "DeepPink"
                        elif ship_length >= 180:
                            label_size = int(base_label_fontsize * 1.3)  # Standard
                            label_suffix = " [STD]"
                            label_color = "Green"
                        else:
                            label_size = int(base_label_fontsize)  # Small / Product

                    # Identify the ship, format the text and symbol
                    clean_name = info["name"].replace('"', "").strip()
                    ship_label = (f'"{clean_name} '
                                  f'({ship_class} {ship_subclass}{label_suffix})" '
                                  f'color={label_color} fontsize={label_size}')

                    f.write(f"{ship_latitude} {ship_longitude} {ship_label} image={ship_symbol}\n")

        logger.info(f"Shipping update complete. {len(selected_ships)} markers written.")


def main():
    import argparse
    from worldmap.lib.logging import setup_logging

    setup_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = WorldMapConfig(args.config)
    updater = ShippingUpdater(config)
    asyncio.run(updater.run())


if __name__ == "__main__":
    main()
