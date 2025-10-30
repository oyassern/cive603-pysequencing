from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict, List, Tuple, Optional
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


def _coerce_payload(body: Any) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    records: Optional[List[Dict[str, Any]]] = None
    dependencies: Optional[Dict[str, Any]] = None

    if isinstance(body, list):
        if all(isinstance(x, dict) for x in body):
            records = body
        else:
            raise HTTPException(status_code=422, detail="Array must contain objects.")
    elif isinstance(body, dict):
        # Activities may be under "activities" or "data"
        data = body.get("activities")
        if data is None:
            data = body.get("data")
        if data is None:
            records = []
        elif isinstance(data, list) and all(isinstance(x, dict) for x in data):
            records = data
        else:
            raise HTTPException(
                status_code=422,
                detail="Body dict 'activities' or 'data' field must be an array of objects.",
            )
        # Dependency dictionary may be supplied under several keys
        dependencies = (
            body.get("dependencies")
            or body.get("dependency_rules")
            or body.get("dictionary")
            or body.get("dependencyRules")
        )
        # If not found at the root, scan inside the data array for a nested dictionary holder
        if dependencies is None and isinstance(records, list):
            for item in records:
                if isinstance(item, dict):
                    for k in ("dependencyRules", "DependencyRules", "dependencies", "dependency_rules", "dictionary"):
                        cand = item.get(k)
                        if isinstance(cand, dict):
                            dependencies = cand
                            break
                if dependencies is not None:
                    break
        if dependencies is not None and not isinstance(dependencies, dict):
            raise HTTPException(status_code=422, detail="Dependencies must be an object if provided.")
    else:
        raise HTTPException(status_code=422, detail="Unsupported body format.")

    return records or [], dependencies


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
    records, dependencies = _coerce_payload(body)
    cleaned = clean_data(records)

    # Save output
    output_latest = os.path.join(data_dir, "clean_output_latest.json")
    output_stamp = os.path.join(archive_dir, f"clean_output_{ts}.json")
    _write_json(output_latest, cleaned)
    _write_json(output_stamp, cleaned)

    dependency_path: Optional[str] = None
    if dependencies is not None:
        dependency_path = os.path.join(data_dir, "dependency_rules.json")
        _write_json(dependency_path, dependencies)

    return {
        "rows": len(cleaned),
        "result": cleaned,
        "files": {
            "input_latest": input_latest,
            "input_archive": input_stamp,
            "output_latest": output_latest,
            "output_archive": output_stamp,
            "dependency_rules": dependency_path,
        },
    }
