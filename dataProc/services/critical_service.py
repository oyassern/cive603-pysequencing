from typing import Any, Dict, List, Optional, Tuple
import json
import os


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _coerce_extra(body: Any) -> List[Dict[str, Any]]:
    # Accept list of activities, or dict with key 'output' possibly as JSON string
    if isinstance(body, list):
        if all(isinstance(x, dict) for x in body):
            return body
        raise ValueError("Body array must contain objects")
    if isinstance(body, dict):
        out = body.get("output")
        if isinstance(out, str):
            try:
                data = json.loads(out)
                if isinstance(data, list) and all(isinstance(x, dict) for x in data):
                    return data
            except Exception:
                pass
        if isinstance(out, list) and all(isinstance(x, dict) for x in out):
            return out
        # Also allow 'activities'
        data = body.get("activities")
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            return data
        # Fallback: if dict itself looks like one activity, wrap
        if {"ScheduleActivityID", "Duration"}.issubset(set(body.keys())):
            return [body]
    raise ValueError("Unsupported extra activities payload format")


def _merge_activities(base: List[Dict[str, Any]], extra: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for rec in base:
        aid = rec.get("ScheduleActivityID")
        if not isinstance(aid, str):
            continue
        if aid not in by_id:
            order.append(aid)
        by_id[aid] = dict(rec)
        # normalize predecessors list
        preds = by_id[aid].get("Predecessors")
        if preds is None:
            by_id[aid]["Predecessors"] = []

    for rec in extra:
        aid = rec.get("ScheduleActivityID")
        if not isinstance(aid, str):
            continue
        if aid not in by_id:
            order.append(aid)
            by_id[aid] = {
                "ScheduleActivityID": aid,
                "Type": rec.get("Type"),
                "Duration": rec.get("Duration"),
                "CWA": rec.get("CWA"),
                "TaskType": rec.get("TaskType") or "Construct",
                "Predecessors": list(rec.get("Predecessors") or []),
            }
        else:
            # merge fields; prefer extra.Duration if provided, union predecessors
            base_rec = by_id[aid]
            if rec.get("Type") is not None:
                base_rec["Type"] = rec.get("Type")
            if rec.get("Duration") is not None:
                base_rec["Duration"] = rec.get("Duration")
            if rec.get("CWA") is not None:
                base_rec["CWA"] = rec.get("CWA")
            if rec.get("TaskType") is not None:
                base_rec["TaskType"] = rec.get("TaskType")
            extra_preds = rec.get("Predecessors") or []
            if isinstance(extra_preds, list):
                base_pred = base_rec.get("Predecessors") or []
                # unique preserve order
                seen = set(base_pred)
                for p in extra_preds:
                    if p not in seen:
                        base_pred.append(p)
                        seen.add(p)
                base_rec["Predecessors"] = base_pred

    return [by_id[a] for a in order]


def _toposort(tasks: Dict[str, Dict[str, Any]]) -> List[str]:
    indeg: Dict[str, int] = {k: 0 for k in tasks.keys()}
    adj: Dict[str, List[str]] = {k: [] for k in tasks.keys()}
    for k, rec in tasks.items():
        for p in rec.get("Predecessors") or []:
            if p in tasks:
                adj[p].append(k)
                indeg[k] += 1
    ready = [n for n, d in indeg.items() if d == 0]
    # stable order
    ready.sort()
    order: List[str] = []
    while ready:
        n = ready.pop(0)
        order.append(n)
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
        ready.sort()
    # append remaining in deterministic way (cycles)
    if len(order) < len(tasks):
        rem = [n for n in tasks.keys() if n not in order]
        rem.sort()
        order.extend(rem)
    return order


def _cpm(tasks_arr: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Try to use pycritical, fall back to manual
    try:
        from pycritical import CriticalPath
        # Expect tasks as dict with id, duration, predecessors
        items = []
        for t in tasks_arr:
            items.append({
                "id": t.get("ScheduleActivityID"),
                "duration": float(t.get("Duration") or 0),
                "predecessors": list(t.get("Predecessors") or []),
            })
        cp = CriticalPath(items)
        result = cp.calculate()
        # Map back to activities
        by_id = {t.get("ScheduleActivityID"): dict(t) for t in tasks_arr}
        for r in result:
            a = by_id.get(r["id"])  # type: ignore
            if a is None:
                continue
            a.update({
                "ES": r.get("ES"),
                "EF": r.get("EF"),
                "LS": r.get("LS"),
                "LF": r.get("LF"),
                "Float": r.get("TF") if "TF" in r else (r.get("LS") - r.get("ES") if r.get("LS") is not None and r.get("ES") is not None else None),
                "Critical": bool(r.get("critical")) if "critical" in r else None,
            })
        return list(by_id.values())
    except Exception:
        # Manual CPM
        tasks = {t.get("ScheduleActivityID"): dict(t) for t in tasks_arr if isinstance(t.get("ScheduleActivityID"), str)}
        # Ensure durations numeric
        for t in tasks.values():
            try:
                t["Duration"] = float(t.get("Duration") or 0)
            except Exception:
                t["Duration"] = 0.0
            if not isinstance(t.get("Predecessors"), list):
                t["Predecessors"] = []
        order = _toposort(tasks)
        # Forward pass
        for k in order:
            preds = tasks[k].get("Predecessors") or []
            es = 0.0
            for p in preds:
                if p in tasks:
                    es = max(es, tasks[p].get("EF") or 0.0)
            d = tasks[k]["Duration"]
            tasks[k]["ES"] = es
            tasks[k]["EF"] = es + d
        # Backward pass
        project_finish = max((tasks[k].get("EF") or 0.0) for k in order) if order else 0.0
        for k in reversed(order):
            # successors
            succ_es = [tasks[s].get("ES") for s, rec in tasks.items() if k in (rec.get("Predecessors") or [])]
            if succ_es:
                lf = min(x for x in succ_es if x is not None)
            else:
                lf = project_finish
            d = tasks[k]["Duration"]
            tasks[k]["LF"] = lf
            tasks[k]["LS"] = lf - d
            tasks[k]["Float"] = (tasks[k]["LS"] - tasks[k]["ES"]) if tasks[k].get("ES") is not None else None
            tasks[k]["Critical"] = abs(tasks[k].get("Float") or 0.0) < 1e-9
        return [tasks[k] for k in order]


def run_critical_job(data_dir: str, extra_body: Any) -> Dict[str, Any]:
    _ensure_dir(data_dir)
    base_path = os.path.join(data_dir, "sequence_output_latest.json")
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Sequence output not found: {base_path}")
    with open(base_path, "r", encoding="utf-8") as f:
        base = json.load(f)
    if isinstance(base, dict):
        base_list = base.get("result") or base.get("activities") or []
    else:
        base_list = base
    if not isinstance(base_list, list):
        raise ValueError("Sequence output must be a list of activities")

    extra_list = _coerce_extra(extra_body)

    merged = _merge_activities(base_list, extra_list)
    cpm = _cpm(merged)

    out_path = os.path.join(data_dir, "critical_output_latest.json")
    _write_json(out_path, cpm)
    return {"result": cpm}

