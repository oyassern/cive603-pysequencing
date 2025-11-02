import json
import os
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _get_box(rec: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    x1 = _safe_float(rec.get("MinOfMinX"))
    x2 = _safe_float(rec.get("MaxOfMaxX"))
    y1 = _safe_float(rec.get("MinOfMinY"))
    y2 = _safe_float(rec.get("MaxOfMaxY"))
    if None in (x1, x2, y1, y2):
        return None
    return (x1, x2, y1, y2)


def _area_overlap_ratio(box1: Tuple[float, float, float, float], box2: Tuple[float, float, float, float]) -> float:
    x1_min, x1_max, y1_min, y1_max = box1
    x2_min, x2_max, y2_min, y2_max = box2
    overlap_x = max(0.0, min(x1_max, x2_max) - max(x1_min, x2_min))
    overlap_y = max(0.0, min(y1_max, y2_max) - max(y1_min, y2_min))
    overlap_area = overlap_x * overlap_y
    a1 = max(0.0, (x1_max - x1_min) * (y1_max - y1_min))
    a2 = max(0.0, (x2_max - x2_min) * (y2_max - y2_min))
    if a1 <= 0 or a2 <= 0:
        return 0.0
    r1 = overlap_area / a1
    r2 = overlap_area / a2
    return max(r1, r2)


def _has_vertical_dependency(pred_max_z: Optional[float], curr_min_z: Optional[float], th1: float, th2: float) -> bool:
    if pred_max_z is None or curr_min_z is None:
        return False
    return (curr_min_z > (pred_max_z - th1)) and (curr_min_z < (pred_max_z + th2))


def _norm_type(s: Optional[str]) -> str:
    return str(s or "").strip().casefold()


def _default_rules() -> Dict[str, List[Dict[str, Any]]]:
    # Mirror the current service defaults
    return {
        "Equipment": [
            {"type": "Concrete", "vert": (0.5, 0.2), "horiz": 0.8},
            {"type": "Piling", "vert": (0.5, 0.2), "horiz": 0.8},
            {"type": "Civil Works", "vert": (0.5, 0.2), "horiz": 0.8},
        ],
        "Grout": [{"type": "Concrete", "vert": (0.2, 0.2), "horiz": 0.8}],
        "Piling": [],
        "Concrete": [],
        "Piping": [{"type": "Concrete", "vert": (0.5, 0.2), "horiz": 0.8}],
        "Piping Insulation": [{"type": "Piping", "horiz": 0.8}],
        "Cable Tray": [{"type": "Concrete", "vert": (0.5, 0.2), "horiz": 0.8}],
        "Electrical": [
            {"type": "Cable Tray", "horiz": 0.6},
            {"type": "UG Conduit", "horiz": 0.6},
        ],
        "Instrumentation": [{"type": "Piping", "horiz": 0.6}],
        "UG Conduit": [{"type": "Civil Works", "horiz": 0.6}],
        "Transformer": [{"type": "Concrete", "vert": (0.5, 0.2), "horiz": 0.8}],
        "Civil Works": [],
    }


def _pair_defaults(cur_type: str, pred_type: str) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
    rules = _default_rules()
    cur_l = _norm_type(cur_type)
    pred_l = _norm_type(pred_type)
    for k, lst in rules.items():
        if _norm_type(k) != cur_l:
            continue
        for r in lst:
            if _norm_type(r.get("type")) == pred_l:
                return (r.get("horiz"), r.get("vert"))
    return (None, None)


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def audit(data_dir: str) -> str:
    # Inputs
    dur_path = os.path.join(data_dir, "duration_output_latest.json")
    seq_path = os.path.join(data_dir, "sequence_output_latest.json")
    rules_path = os.path.join(data_dir, "dependency_rules.json")

    duration = _load_json(dur_path)
    seq = _load_json(seq_path)
    rules = _load_json(rules_path) if os.path.exists(rules_path) else None

    if isinstance(seq, dict):
        nodes = seq.get("result") or seq.get("activities") or []
    else:
        nodes = seq

    # Index duration by CWA and name
    by_cwa: Dict[str, List[Dict[str, Any]]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for rec in duration:
        cwa = str(rec.get("CWA") or "").strip()
        by_cwa.setdefault(cwa, []).append(rec)
        name = rec.get("Element Name")
        if name:
            by_name[name] = rec

    no_pred_nodes = [n for n in nodes if not n.get("Predecessors")]

    lines: List[str] = []
    lines.append(f"# Sequence Audit Log\n")
    lines.append(f"Data directory: `{data_dir}`\n")
    lines.append(f"Total activities: {len(nodes)}\n")
    lines.append(f"Activities without predecessors: {len(no_pred_nodes)}\n")
    lines.append("")

    for n in no_pred_nodes:
        name = n.get("ScheduleActivityID")
        rec = by_name.get(name, {})
        cwa = str(rec.get("CWA") or "").strip()
        cur_type = str(rec.get("Type") or n.get("Type") or "").strip()
        cur_box = _get_box(rec)
        cur_minz = _safe_float(rec.get("MinOfMinZ"))
        lines.append(f"## {name}\n")
        lines.append(f"- Type: {cur_type}")
        lines.append(f"- CWA: {cwa}")

        # Determine allowed predecessor types
        allowed: List[str] = []
        if isinstance(rules, dict):
            raw = None
            if cur_type in rules:
                raw = rules.get(cur_type)
            else:
                # case-insensitive match
                for k, v in rules.items():
                    if _norm_type(k) == _norm_type(cur_type):
                        raw = v
                        break
            if isinstance(raw, list):
                seen = set()
                for p in raw:
                    key = _norm_type(str(p))
                    if key not in seen:
                        seen.add(key)
                        allowed.append(str(p))
        # If no provided, fall back to defaults list
        if not allowed:
            allowed = [r.get("type") for r in _default_rules().get(cur_type, [])]

        if not allowed:
            lines.append("- No allowed predecessor types configured (skipping checks).\n")
            continue

        for ptype in allowed:
            # thresholds
            th_h, th_v = _pair_defaults(cur_type, ptype)
            # Ignore vertical rule for Equipment for now
            if _norm_type(cur_type) == "equipment":
                th_v = None
            if th_h is None:
                th_h = 0.8

            # candidates in same CWA and type
            cands = [r for r in by_cwa.get(cwa, []) if _norm_type(r.get("Type")) == _norm_type(ptype)]
            if not cands:
                lines.append(f"- {ptype}: no candidates of this type in same CWA")
                continue

            # Horizontal filter
            horiz_pass = []
            for cand in cands:
                b2 = _get_box(cand)
                if not cur_box or not b2:
                    continue
                if _area_overlap_ratio(cur_box, b2) >= float(th_h):
                    horiz_pass.append(cand)
            if not horiz_pass:
                lines.append(f"- {ptype}: {len(cands)} candidates found, none pass horizontal >= {th_h}")
                continue

            # Vertical check (if any)
            if th_v is not None:
                vpass = []
                for cand in horiz_pass:
                    pred_max = _safe_float(cand.get("MaxOfMaxZ"))
                    if _has_vertical_dependency(pred_max, cur_minz, th_v[0], th_v[1]):
                        vpass.append(cand)
                if not vpass:
                    lines.append(f"- {ptype}: horizontal passed but vertical not within ({th_v[0]}, {th_v[1]})")
                    continue
                else:
                    lines.append(f"- {ptype}: has candidates that pass both checks but none selected → review selection logic")
            else:
                lines.append(f"- {ptype}: has candidates passing horizontal >= {th_h} (no vertical check required) but none selected → review selection logic")

        lines.append("")

    return "\n".join(lines)


def main():
    # Default to docker-setup/pyproc-data which is the mounted data folder in this repo
    data_dir = os.environ.get("SEQ_AUDIT_DATA", os.path.join("docker-setup", "pyproc-data"))
    report = audit(data_dir)
    out_path = os.path.join(data_dir, "log.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Wrote audit log to {out_path}")


if __name__ == "__main__":
    main()
