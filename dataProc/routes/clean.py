from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict, List
from datetime import datetime
import json
import os

from services.clean_service import clean_data


router = APIRouter(prefix="/v1", tags=["clean"])


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _coerce_records(body: Any) -> List[Dict[str, Any]]:
    if isinstance(body, list):
        if all(isinstance(x, dict) for x in body):
            return body
        raise HTTPException(status_code=422, detail="Array must contain objects.")
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            return data
    raise HTTPException(
        status_code=422,
        detail=(
            "Body must be either an array of objects or an object "
            "like { 'data': [ {...}, ... ] }."
        ),
    )


@router.post("/clean")
def clean_endpoint(body: Any = Body(...)):
    # Prepare storage paths
    data_dir = os.path.join(os.getcwd(), "data")
    archive_dir = os.path.join(data_dir, "archive")
    _ensure_dir(data_dir)
    _ensure_dir(archive_dir)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Save raw input
    input_latest = os.path.join(data_dir, "clean_input_latest.json")
    input_stamp = os.path.join(archive_dir, f"clean_input_{ts}.json")
    _write_json(input_latest, body)
    _write_json(input_stamp, body)

    # Coerce and clean
    records = _coerce_records(body)
    cleaned = clean_data(records)

    # Save output
    output_latest = os.path.join(data_dir, "clean_output_latest.json")
    output_stamp = os.path.join(archive_dir, f"clean_output_{ts}.json")
    _write_json(output_latest, cleaned)
    _write_json(output_stamp, cleaned)

    return {
        "rows": len(cleaned),
        "result": cleaned,
        "files": {
            "input_latest": input_latest,
            "input_archive": input_stamp,
            "output_latest": output_latest,
            "output_archive": output_stamp,
        },
    }

