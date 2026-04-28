import os
import json
import logging

logger = logging.getLogger(__name__)


def get_vessel_class(code):
    if not code or code == 0:
        return "Vessel"

    # Specific/Specialized Codes
    special_codes = {
        30: "Fishing Vessel",
        31: "Towing Vessel",
        32: "Towing (Large/Towed)",
        33: "Dredging/Underwater Ops",
        34: "Diving Ops",
        35: "Military Ops",
        36: "Sailing Vessel",
        37: "Pleasure Craft",
        50: "Pilot Vessel",
        51: "Search and Rescue (SAR)",
        52: "Tug",
        53: "Port Tender",
        54: "Anti-Pollution Equipment",
        55: "Law Enforcement",
        58: "Medical Transport",
        59: "Non-Combatant (Neutral State)",
    }

    if code in special_codes:
        return special_codes[code]

    vessel_classes = {
        1: "WIG (Wing In Ground)",
        2: "WIG (Wing In Ground)",
        4: "High Speed Craft",
        6: "Passenger Ship",
        7: "Cargo",
        8: "Tanker",
        9: "Other",
    }

    class_digit = code // 10
    return vessel_classes.get(class_digit, f"Vessel (Type {code})")

def get_vessel_subclass(code):
    if not code or code == 0:
        return ""

    vessel_subclasses = {
        1: "Hazardous A",
        2: "Hazardous B",
        3: "Hazardous C",
        4: "Hazardous D"
    }
    sub_digit = code % 10
    return vessel_subclasses.get(sub_digit, "")


class ShipCache:
    def __init__(self, db_path):
        self.db_path = db_path
        self.data = self._load()
        self._migrate_and_clean()

    def _load(self):
        if os.path.exists(self.db_path) and os.path.getsize(self.db_path) > 0:
            try:
                with open(self.db_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Corrupt database at {self.db_path}")
        return {}

    def _migrate_and_clean(self):
        """
        Migrate database to new schema
        """
        migrated_count = 0
        for mmsi, ship in self.data.items():
            updated = False

            # Migrate Dimensions refactor
            dims = ship.get("dimensions")
            if isinstance(dims, dict) and ("length" in dims and "beam" in dims):
                length = int(dims.get("length", 0))
                beam = int(dims.get("beam", 0))
                del ship["dimensions"]
                ship["length"] = length
                ship["beam"] = beam
                updated = True

            # Remove type_name
            if "type_name" in ship:
                del ship["type_name"]
                updated = True

            if updated:
                migrated_count += 1

        if migrated_count > 0:
            self.save()
            logger.info(f"Synchronized and migrated {migrated_count} ship records.")

    def save(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(self.data, f, indent=4)

    def update_from_static(self, mmsi, metadata, body):
        """
        Updates cache from a ShipStaticData message.
        Preserves existing data if the new message is missing fields.
        """
        mmsi = str(mmsi)
        current_ship = self.data.get(mmsi, {})

        # Basic Info
        new_name = (
            metadata.get("ShipName")
            or body.get("Name")
            or current_ship.get("name", "Unknown")
        ).strip()
        new_type_code = (
            body.get("Type") or body.get("VesselType") or current_ship.get("type", 0)
        )

        # Draught & History
        new_draught = body.get("MaximumStaticDraught", 0.0)
        previous_draught = current_ship.get("draught", 0.0)

        if 0.0 < previous_draught != new_draught != 0.0:
            final_prev = previous_draught
        else:
            final_prev = current_ship.get("prev_draught", 0.0)

        final_draught = new_draught if new_draught != 0.0 else previous_draught

        # Dimensions
        raw_dims = body.get("Dimension", {})
        if raw_dims:
            new_length = raw_dims.get("A", 0) + raw_dims.get("B", 0)
            new_beam = raw_dims.get("C", 0) + raw_dims.get("D", 0)
        else:
            new_length = new_beam = 0

        # Update dimensions if the new data is non-zero
        current_length = current_ship.get("length", 0)
        current_beam = current_ship.get("beam", 0)
        update_length = new_length if new_length > 0 else current_length
        update_beam = new_beam if new_beam > 0 else current_beam

        # Update the master dictionary
        self.data[mmsi] = {
            "name": new_name,
            "type": new_type_code,
            "imo": body.get("ImoNumber") or current_ship.get("imo", 0),
            "callsign": (body.get("CallSign") or current_ship.get("callsign", "")).strip(),
            "draught": final_draught,
            "prev_draught": final_prev,
            "length": update_length,
            "beam": update_beam,
        }
        return True
