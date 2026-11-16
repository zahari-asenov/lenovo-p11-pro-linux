#!/usr/bin/env python3
"""Load archived factory CAL_R bytes using the stock Android HAL encoding."""
import argparse
import json
from pathlib import Path
import subprocess


def decode_record(record):
    data = bytes.fromhex(record)
    if len(data) != 4 or not 8113 <= int.from_bytes(data, "big") <= 11328:
        raise ValueError("Factory CAL_R is outside the stock HAL accepted range")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path,
                        default=Path("/var/lib/j706f/speaker-calibration.json"))
    args = parser.parse_args()
    records = json.loads(args.file.read_text())["cal_r"]
    if len(records) != 4:
        raise ValueError("Exactly four factory calibration records are required")
    # Validate every record before changing any amplifier.
    values = [decode_record(record) for record in records]
    for number, value in enumerate(values, 1):
        subprocess.run([
            "amixer", "-c", "0", "cset",
            f"name=SPK{number} DSP1 Protection cd CAL_R",
            ",".join(f"0x{byte:02x}" for byte in value),
        ], check=True, stdout=subprocess.DEVNULL)
        print(f"SPK{number}: factory CAL_R loaded")


if __name__ == "__main__":
    main()
