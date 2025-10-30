from typing import Any, Dict, List, Optional, Tuple
import json
import os
from datetime import datetime


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


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


def _has_vertical_dependency(pred_max_z: Optional[float], curr_min_z: Optional[float], th1: float = 0.5, th2: float = 0.2) -> bool:
    if pred_max_z is None or curr_min_z is None:
        return False
    return (curr_min_z > (pred_max_z - th1)) and (curr_min_z < (pred_max_z + th2))


def _choose_metric_type(act_type: str) -> str:
    if act_type in ("Concrete", "Grout", "Civil Works", "Transformer"):
        return "volume"
    if act_type in ("Piping", "Piping Insulation", "Cable Tray", "UG Conduit"):
        return "run"
    if act_type in ("Electrical", "Instrumentation"):
        return "area"
    if act_type == "Piling":
        return "height"
    return "volume"


def _run_length(rec: Dict[str, Any]) -> float:
    l = _safe_float(rec.get("Length")) or 0.0
    w = _safe_float(rec.get("Width")) or 0.0
    return max(float(l), float(w))


def _area(rec: Dict[str, Any]) -> float:
    l = _safe_float(rec.get("Length")) or 0.0
    w = _safe_float(rec.get("Width")) or 0.0
    return float(l) * float(w)


def _height(rec: Dict[str, Any]) -> float:
    return _safe_float(rec.get("Height")) or 0.0


def _norm_type(s: Optional[str]) -> str:
    return str(s or "").strip().casefold()


def _sequence_group(records: List[Dict[str, Any]], type_rules: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    # Define predecessor rules by current activity type (defaults)
    default_rules: Dict[str, List[Dict[str, Any]]] = {
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

    # Build a case-insensitive view of default rules for lookup
    def _default_rule_pair(cur: str, pred: str) -> Optional[Dict[str, Any]]:
        cur_l = _norm_type(cur)
        pred_l = _norm_type(pred)
        # find by scanning the default list
        for k, lst in default_rules.items():
            if _norm_type(k) == cur_l:
                for r in lst:
                    if _norm_type(r.get("type")) == pred_l:
                        return r
        return None

    # Precompute boxes and elevations
    idx = {i: rec for i, rec in enumerate(records)}
    boxes = {i: _get_box(rec) for i, rec in idx.items()}
    minz = {i: _safe_float(rec.get("MinOfMinZ")) for i, rec in idx.items()}
    maxz = {i: _safe_float(rec.get("MaxOfMaxZ")) for i, rec in idx.items()}

    edges: List[Dict[str, Any]] = []

    for i, rec in idx.items():
        cur_type = rec.get("Type") or ""
        cur_name = rec.get("Element Name")
        cur_box = boxes.get(i)
        cur_minz = minz.get(i)
        # Choose rule list: use provided type_rules if available, else defaults
        rule_list: List[Dict[str, Any]]
        if isinstance(type_rules, dict):
            # Support case-insensitive keys in provided dict
            desired_preds: Optional[List[Any]] = None
            # try direct, then case-insensitive scan
            if cur_type in type_rules:
                desired_preds = type_rules.get(cur_type)  # type: ignore
            else:
                for k, v in type_rules.items():
                    if _norm_type(k) == _norm_type(cur_type):
                        desired_preds = v  # type: ignore
                        break
            if isinstance(desired_preds, list):
                # Normalize and deduplicate predecessor types by case-insensitive name
                seen_pred_types = set()
                norm_preds: List[str] = []
                for p in desired_preds:
                    p_name = str(p)
                    key = _norm_type(p_name)
                    if key in seen_pred_types:
                        continue
                    seen_pred_types.add(key)
                    norm_preds.append(p_name)

                tmp: List[Dict[str, Any]] = []
                for p_name in norm_preds:
                    base = _default_rule_pair(cur_type, p_name)
                    if base is not None:
                        tmp.append(dict(base))
                    else:
                        # Default behavior: require horizontal overlap 0.8, no vertical requirement
                        tmp.append({"type": p_name, "horiz": 0.8})
                rule_list = tmp
            else:
                rule_list = default_rules.get(cur_type, [])
        else:
            rule_list = default_rules.get(cur_type, [])
        # Evaluate each predecessor type exactly once; all checks must pass
        chosen_preds: List[str] = []
        for rule in rule_list:
            pred_type = rule.get("type")
            th_h = rule.get("horiz")
            th_vert = rule.get("vert")  # tuple
            best_score = -1.0
            best_pred_name: Optional[str] = None
            for j, cand in idx.items():
                if i == j:
                    continue
                if _norm_type(cand.get("Type")) != _norm_type(pred_type):
                    continue
                # Horizontal check
                if th_h is not None:
                    b2 = boxes.get(j)
                    if not cur_box or not b2:
                        continue
                    overlap = _area_overlap_ratio(cur_box, b2)
                    if overlap < float(th_h):
                        continue
                # Vertical check
                if th_vert is not None:
                    pred_max = maxz.get(j)
                    if not _has_vertical_dependency(pred_max, cur_minz, th_vert[0], th_vert[1]):
                        continue
                # Score: prefer closer in Z and higher overlap
                score = 0.0
                if th_vert is not None and maxz.get(j) is not None and cur_minz is not None:
                    dz = abs(cur_minz - maxz[j])
                    score -= dz  # smaller better
                if th_h is not None and cur_box and boxes.get(j):
                    score += _area_overlap_ratio(cur_box, boxes[j])
                if score > best_score:
                    best_score = score
                    best_pred_name = cand.get("Element Name")
            if best_pred_name:
                edges.append({
                    "ScheduleActivityID": cur_name,
                    "Predecessor": best_pred_name,
                    "Rel": "FS",
                    "TaskType": "Construct",
                })
                chosen_preds.append(best_pred_name)

    return edges


def compute_sequence(duration_records: List[Dict[str, Any]], type_rules: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    # Group by CWA and sequence within each
    by_cwa: Dict[str, List[Dict[str, Any]]] = {}
    for rec in duration_records:
        cwa = str(rec.get("CWA") or "").strip()
        if not cwa:
            # Skip records without CWA
            continue
        by_cwa.setdefault(cwa, []).append(rec)

    all_edges: List[Dict[str, Any]] = []
    for cwa, group in by_cwa.items():
        edges = _sequence_group(group, type_rules=type_rules)
        all_edges.extend(edges)
    return all_edges


def _load_dependency_rules(data_dir: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(data_dir, DEPENDENCY_FILENAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _build_activity_list_ordered(
    duration_records: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # Deduplicate by first appearance and capture original order index
    index_by_name: Dict[str, int] = {}
    rec_by_name: Dict[str, Dict[str, Any]] = {}
    for idx, rec in enumerate(duration_records):
        name = rec.get("Element Name")
        if not name:
            continue
        if name not in index_by_name:
            index_by_name[name] = idx
            rec_by_name[name] = rec

    # Build graph from edges for topological order
    adj: Dict[str, List[str]] = {n: [] for n in index_by_name.keys()}
    indeg: Dict[str, int] = {n: 0 for n in index_by_name.keys()}
    for e in edges:
        cur = e.get("ScheduleActivityID")
        pred = e.get("Predecessor")
        if isinstance(cur, str) and isinstance(pred, str):
            if pred in adj and cur in indeg:
                adj[pred].append(cur)
                indeg[cur] += 1

    # Kahn's algorithm, stable by original order
    ready = [n for n, d in indeg.items() if d == 0]
    ready.sort(key=lambda n: index_by_name.get(n, 10**9))
    ordered: List[str] = []
    while ready:
        n = ready.pop(0)
        ordered.append(n)
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
        ready.sort(key=lambda x: index_by_name.get(x, 10**9))

    # Append any remaining nodes (cycles or disconnected), keeping original order
    if len(ordered) < len(index_by_name):
        remaining = [n for n in index_by_name.keys() if n not in ordered]
        remaining.sort(key=lambda n: index_by_name[n])
        ordered.extend(remaining)

    # Build node dicts in the computed order
    nodes: List[Dict[str, Any]] = []
    for name in ordered:
        rec = rec_by_name.get(name, {})
        nodes.append({
            "ScheduleActivityID": name,
            "Type": rec.get("Type"),
            "Duration": rec.get("Duration"),
            "CWA": rec.get("CWA"),
            "TaskType": "Construct",
        })
    return nodes


# Backward-compatibility shim: legacy name without edges ordering
def _build_activity_list(duration_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index_by_name: Dict[str, int] = {}
    nodes: List[Dict[str, Any]] = []
    for idx, rec in enumerate(duration_records):
        name = rec.get("Element Name")
        if not name or name in index_by_name:
            continue
        index_by_name[name] = idx
        nodes.append({
            "ScheduleActivityID": name,
            "Type": rec.get("Type"),
            "Duration": rec.get("Duration"),
            "CWA": rec.get("CWA"),
            "TaskType": "Construct",
        })
    return nodes


def run_sequence_job(data_dir: str) -> Dict[str, Any]:
    _ensure_dir(data_dir)
    archive_dir = os.path.join(data_dir, "archive")
    _ensure_dir(archive_dir)

    source_path = os.path.join(data_dir, "duration_output_latest.json")
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Duration output not found: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        duration_records = json.load(f)
    if not isinstance(duration_records, list):
        raise ValueError("Duration output is not a list of records")

    dependency_rules = _load_dependency_rules(data_dir)

    # Compute edges directly; rules should prevent duplicates inherently
    edges = compute_sequence(duration_records, type_rules=dependency_rules)

    # Build ordered activity list (includes those without predecessors)
    activities = _build_activity_list_ordered(duration_records, edges)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    # Write ordered activities as the sequence output
    out_latest = os.path.join(data_dir, "sequence_output_latest.json")
    out_stamp = os.path.join(archive_dir, f"sequence_output_{ts}.json")
    _write_json(out_latest, activities)
    _write_json(out_stamp, activities)
    # Also persist edges separately for reference
    edges_latest = os.path.join(data_dir, "sequence_edges_latest.json")
    edges_stamp = os.path.join(archive_dir, f"sequence_edges_{ts}.json")
    _write_json(edges_latest, edges)
    _write_json(edges_stamp, edges)

    return {
        "edges": len(edges),
        "result": activities,
        "files": {
            "source_duration": source_path,
            "output_latest": out_latest,
            "output_archive": out_stamp,
            "edges_latest": edges_latest,
            "edges_archive": edges_stamp,
            "dependency_rules": os.path.join(data_dir, DEPENDENCY_FILENAME) if dependency_rules is not None else None,
        },
    }
DEPENDENCY_FILENAME = "dependency_rules.json"
