from typing import Any, Dict, List, Optional, Tuple
import json
import os
import re
from datetime import datetime
import math


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _extract_activity_type(name: Optional[str]) -> str:
    if not name:
        return ""
    s = str(name)
    # Normalize underscores/spaces
    s_norm = re.sub(r"[_\s]+", "_", s.strip())
    # Prefer patterns like ..._Install_<Type>...
    m = re.search(r"_Install_([A-Za-z0-9_]+)", s_norm, flags=re.IGNORECASE)
    if m:
        raw = m.group(1)
        return raw.replace("_", " ").strip()
    # Civil Works explicit token
    if re.search(r"(^|_)civil[_ ]works($|_)", s_norm, flags=re.IGNORECASE):
        return "Civil Works"
    # Fall back to Set_<...> → treat as Equipment
    m2 = re.search(r"_Set_([A-Za-z0-9_]+)", s_norm, flags=re.IGNORECASE)
    if m2:
        return "Equipment"
    return ""


def _is_set_activity(name: Optional[str]) -> bool:
    if not name:
        return False
    s = str(name)
    s_norm = re.sub(r"[_\s]+", "_", s.strip())
    return re.search(r"_Set_([A-Za-z0-9_]+)", s_norm, flags=re.IGNORECASE) is not None


INSTALL_EXPONENTS: Dict[str, float] = {
    # Exponents used with relative metrics per type
    "Concrete": 0.90,
    "Grout": 0.80,
    "Piling": 0.80,
    "Cable Tray": 0.60,
    "Electrical": 0.50,
    "Instrumentation": 0.50,
    "Piping": 0.70,
    "Piping Insulation": 0.65,
    "UG Conduit": 0.70,
    "Transformer": 0.50,
    "Civil Works": 0.90,
}

# Median-based base durations (days) per type at median size
INSTALL_BASE_DAYS: Dict[str, float] = {
    "Concrete": 3.0,
    "Grout": 0.5,
    "Piling": 2.0,
    "Cable Tray": 3.0,
    "Electrical": 5.0,
    "Instrumentation": 4.0,
    "Piping": 4.0,
    "Piping Insulation": 3.0,
    "UG Conduit": 3.0,
    "Transformer": 1.5,
    "Civil Works": 3.0,
}

# Equipment (Set_*) sub-type classification and rules
EQUIP_SUBTYPE_BASE_DAYS: Dict[str, float] = {
    "module_valve": 0.5,
    "module_motor_pump_fan": 1.5,
    "module_ahu": 1.5,
    "module_transformer": 1.5,
    "module_switchgear": 2.0,
    "module_vessel": 2.0,
    "module_tank": 2.5,
    "module_vaporizer_heater": 2.0,
    "module_compressor": 2.5,
    "module_crane": 1.0,
    "module_weighscale": 1.0,
    "module_building_equipment": 3.0,
    "module_other": 1.5,
}

EQUIP_SUBTYPE_EXPONENT: Dict[str, float] = {
    # Generally shallow scaling on volume for equipment sets
    "module_valve": 0.40,
    "module_motor_pump_fan": 0.50,
    "module_ahu": 0.50,
    "module_transformer": 0.50,
    "module_switchgear": 0.60,
    "module_vessel": 0.60,
    "module_tank": 0.60,
    "module_vaporizer_heater": 0.60,
    "module_compressor": 0.60,
    "module_crane": 0.40,
    "module_weighscale": 0.40,
    "module_building_equipment": 0.60,
    "module_other": 0.50,
}


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        x = float(val)
        return x
    except Exception:
        return None


def _volume_for_record(rec: Dict[str, Any]) -> float:
    # Prefer Volume if present
    v = _safe_float(rec.get("Volume"))
    if v is not None:
        return max(0.0, v)
    # Fallback: Height*Length*Width
    h = _safe_float(rec.get("Height"))
    l = _safe_float(rec.get("Length"))
    w = _safe_float(rec.get("Width"))
    if h is not None and l is not None and w is not None:
        try:
            return max(0.0, float(h) * float(l) * float(w))
        except Exception:
            pass
    # Fallback: bounding box extents if available
    x1 = _safe_float(rec.get("MinOfMinX")); x2 = _safe_float(rec.get("MaxOfMaxX"))
    y1 = _safe_float(rec.get("MinOfMinY")); y2 = _safe_float(rec.get("MaxOfMaxY"))
    z1 = _safe_float(rec.get("MinOfMinZ")); z2 = _safe_float(rec.get("MaxOfMaxZ"))
    if None not in (x1, x2, y1, y2, z1, z2):
        dx = max(0.0, float(x2) - float(x1))
        dy = max(0.0, float(y2) - float(y1))
        dz = max(0.0, float(z2) - float(z1))
        return max(0.0, dx * dy * dz)
    return 0.0


def _run_length_for_record(rec: Dict[str, Any]) -> float:
    # Approximate linear run by the larger of Length/Width
    l = _safe_float(rec.get("Length")) or 0.0
    w = _safe_float(rec.get("Width")) or 0.0
    return max(float(l), float(w))


def _plan_area_for_record(rec: Dict[str, Any]) -> float:
    l = _safe_float(rec.get("Length")) or 0.0
    w = _safe_float(rec.get("Width")) or 0.0
    return max(0.0, float(l) * float(w))


def _height_for_record(rec: Dict[str, Any]) -> float:
    h = _safe_float(rec.get("Height")) or 0.0
    return float(h)


def _classify_module_subtype(name: Optional[str]) -> str:
    if not name:
        return "module_other"
    s = str(name).upper()
    # Order matters (more specific first)
    if re.search(r"(^|[-_])V\d+($|[-_])", s) or re.search(r"FV-\d+|PV-\d+", s):
        return "module_valve"
    if re.search(r"\b(AHU)\b", s):
        return "module_ahu"
    if re.search(r"XFMER|XFMR|TRANSFORMER", s):
        return "module_transformer"
    if re.search(r"SWITCHGEAR|SWGR|GEAR|MCC|PANEL\b|\bMV\b|\bLV\b", s):
        return "module_switchgear"
    if re.search(r"VAPORIZ(ER|OR)|HEATER|TRIM HEATER|STEAM SPARGED", s):
        return "module_vaporizer_heater"
    if re.search(r"COMPRESSOR|BOOSTER", s):
        return "module_compressor"
    if re.search(r"TANK|STORAGE|BUFFER|DUMP", s):
        return "module_tank"
    if re.search(r"VESSEL|ADSORBER|SILENCER\b", s):
        return "module_vessel"
    if re.search(r"CRANE", s):
        return "module_crane"
    if re.search(r"WEIGH|SCALE", s):
        return "module_weighscale"
    if re.search(r"MAC|BAC|PUMP|FAN", s):
        return "module_motor_pump_fan"
    if re.search(r"BUILDING", s):
        return "module_building_equipment"
    return "module_other"


def _median(values: List[float]) -> float:
    vals = sorted([v for v in values if v is not None])
    n = len(vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


def _quantiles(values: List[float], q: List[float]) -> List[float]:
    # Simple linear interpolation quantiles (inclusive)
    vals = sorted([v for v in values if v is not None])
    n = len(vals)
    out: List[float] = []
    if n == 0:
        return [0.0 for _ in q]
    for qi in q:
        if qi <= 0:
            out.append(vals[0])
            continue
        if qi >= 1:
            out.append(vals[-1])
            continue
        pos = qi * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        out.append(vals[lo] * (1 - frac) + vals[hi] * frac)
    return out


def _require_positive_float(val: Any, name: str) -> float:
    # Retained for compatibility but unused after hardcoding K
    try:
        x = float(val)
        if x > 0:
            return x
    except Exception:
        pass
    raise ValueError(f"Parameter {name} must be a positive number")


def compute_durations(
    cleaned_records: List[Dict[str, Any]],
    params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    # Hardcode global scale factor K so median-sized activities have Duration = K
    # Per request, do not require parameters from the client.
    K = 1.0

    # Compute per-type metrics for Install types
    # and module-wide statistics for Set_* activities
    type_metric_values: Dict[str, List[float]] = {}
    set_vols: List[float] = []

    # First pass: collect volumes
    for rec in cleaned_records:
        name = rec.get("Element Name")
        v = _volume_for_record(rec)
        if _is_set_activity(name):
            set_vols.append(v)
        else:
            t = _extract_activity_type(name)
            if t:
                # Choose metric based on type
                if t in ["Concrete", "Grout", "Civil Works", "Transformer"]:
                    metric = v
                elif t in ["Piping", "Piping Insulation", "Cable Tray", "UG Conduit"]:
                    metric = _run_length_for_record(rec)
                elif t in ["Electrical", "Instrumentation"]:
                    metric = _plan_area_for_record(rec)
                elif t == "Piling":
                    metric = _height_for_record(rec)
                else:
                    metric = v
                type_metric_values.setdefault(t, []).append(metric)

    # Compute medians for each install type metric
    type_to_median: Dict[str, float] = {t: _median(vs) for t, vs in type_metric_values.items()}
    # Module quantiles and median
    set_median = _median(set_vols)
    q1, q3 = _quantiles(set_vols, [0.25, 0.75]) if set_vols else (0.0, 0.0)

    out: List[Dict[str, Any]] = []
    for rec in cleaned_records:
        name = rec.get("Element Name")
        act_type = _extract_activity_type(name)
        v = _volume_for_record(rec)

        if _is_set_activity(name):
            # Equipment: classify subtype
            subtype = _classify_module_subtype(name)
            beta = EQUIP_SUBTYPE_EXPONENT.get(subtype, 0.50)
            base_days = EQUIP_SUBTYPE_BASE_DAYS.get(subtype, 1.5)
            # Normalize by module median volume
            denom = set_median if set_median > 0 else 1.0
            duration_days = base_days * ((v / denom) ** beta if denom > 0 else 1.0)
            # Clamp to reasonable bounds for equipment
            min_d, max_d = 0.25, 7.0
            duration_days = max(min_d, min(duration_days, max_d))
        else:
            # Install_* types: choose metric and apply exponent with median-based base days
            beta = INSTALL_EXPONENTS.get(act_type)
            if beta is None:
                raise ValueError(f"Missing exponent for type '{act_type or 'UNKNOWN'}' in INSTALL_EXPONENTS")
            base_days = INSTALL_BASE_DAYS.get(act_type, 1.0)
            # Metric selection
            if act_type in ["Concrete", "Grout", "Civil Works", "Transformer"]:
                metric = v
            elif act_type in ["Piping", "Piping Insulation", "Cable Tray", "UG Conduit"]:
                metric = _run_length_for_record(rec)
            elif act_type in ["Electrical", "Instrumentation"]:
                metric = _plan_area_for_record(rec)
            elif act_type == "Piling":
                metric = _height_for_record(rec)
            else:
                metric = v
            denom = type_to_median.get(act_type, 0.0)
            denom = denom if denom > 0 else 1.0
            duration_days = base_days * ((metric / denom) ** beta if denom > 0 else 1.0)
            # Reasonable bounds per type
            bounds = {
                "Concrete": (0.5, 10.0),
                "Civil Works": (0.5, 10.0),
                "Grout": (0.25, 2.0),
                "Piling": (0.5, 8.0),
                "Piping": (1.0, 10.0),
                "Piping Insulation": (0.5, 8.0),
                "Cable Tray": (0.5, 8.0),
                "UG Conduit": (1.0, 8.0),
                "Electrical": (1.0, 12.0),
                "Instrumentation": (1.0, 10.0),
                "Transformer": (0.5, 5.0),
            }
            min_d, max_d = bounds.get(act_type, (0.25, 15.0))
            duration_days = max(min_d, min(duration_days, max_d))

        # Per-type adjustments
        if act_type == "Concrete":
            # Decrease Concrete by 50%
            duration_days *= 0.5

        # Post-processing: increase by 50%, minimum 1 day, and ceil to integer
        duration_days = math.ceil(max(1.0, duration_days * 1.5))

        rec_out = dict(rec)
        # Remove unwanted coordinate fields
        for k in [
            "X Coordinate",
            "Y Coordinate",
            "Z Coordinate",
            "Position X",
            "Position Y",
            "Position Z",
        ]:
            rec_out.pop(k, None)
        # Add Type and Duration
        rec_out["Type"] = act_type
        rec_out["Duration"] = duration_days
        out.append(rec_out)
    return out


def run_duration_job(
    data_dir: str,
    rules: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ensure_dir(data_dir)
    archive_dir = os.path.join(data_dir, "archive")
    _ensure_dir(archive_dir)

    source_path = os.path.join(data_dir, "clean_output_latest.json")
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Clean output not found: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        cleaned = json.load(f)
    if not isinstance(cleaned, list):
        raise ValueError("Clean output is not a list of records")

    enriched = compute_durations(cleaned, None)

    # Validate all records have Duration
    missing = [i for i, r in enumerate(enriched) if "Duration" not in r or r["Duration"] is None]
    if missing:
        raise ValueError(f"Some activities missing Duration: indices {missing[:5]}{'...' if len(missing)>5 else ''}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_latest = os.path.join(data_dir, "duration_output_latest.json")
    out_stamp = os.path.join(archive_dir, f"duration_output_{ts}.json")
    _write_json(out_latest, enriched)
    _write_json(out_stamp, enriched)

    return {
        "rows": len(enriched),
        "result": enriched,
        "files": {
            "source_clean": source_path,
            "output_latest": out_latest,
            "output_archive": out_stamp,
        },
    }
