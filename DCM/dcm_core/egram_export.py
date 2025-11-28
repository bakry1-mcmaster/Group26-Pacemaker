"""Export helpers to generate an EgramRecord JSON from current DCM state.

Reads `dcm_params.json` and `dcm_mode.json` from the working directory and
produces a minimal EgramRecord (no samples) that includes meta, mode, and a
ParamsRecorded. Useful for D1 appendices and traceability.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .egram_data import EgramRecord, ParamsRecorded, new_template


PARAMS_FILE = "dcm_params.json"
MODE_FILE = "dcm_mode.json"


def export_current_to_json(
    output_path: str,
    session_id: str,
    user: Optional[str] = None,
    dcm_version: Optional[str] = None,
) -> str:
    """Create a minimal EgramRecord JSON capturing current params + mode.

    Returns the written file path.
    """
    # Load params
    params_data = {}
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE, "r") as f:
            params_data = json.load(f)
    snap = ParamsRecorded(**params_data) if params_data else ParamsRecorded()

    # Load mode
    mode = None
    if os.path.exists(MODE_FILE):
        with open(MODE_FILE, "r") as f:
            mode_data = json.load(f)
            mode = (mode_data or {}).get("mode")

    # Build record
    rec: EgramRecord = new_template(
        session_id=session_id,
        mode=mode,
        params=snap,
        user=user,
        source="hardware",
    )
    if dcm_version:
        rec.meta.dcm_version = dcm_version

    # No blocks/samples yet; this is a template with meta + params
    payload = rec.to_json(indent=2)
    with open(output_path, "w") as f:
        f.write(payload)
    return os.path.abspath(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export current DCM params+mode to an EgramRecord JSON template")
    parser.add_argument("session_id", help="Unique session identifier")
    parser.add_argument("output", help="Path to write JSON (e.g., egram_template.json)")
    parser.add_argument("--user", default=None, help="Username to record in meta")
    parser.add_argument("--version", default=None, help="DCM version string")
    args = parser.parse_args()

    path = export_current_to_json(
        output_path=args.output,
        user=args.user,
        dcm_version=args.version,
    )
    print(path)

