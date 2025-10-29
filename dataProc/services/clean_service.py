from typing import List, Dict, Any, Optional
import re


AUTO_GEOM_PREFIX = "AutoCAD Geometry."


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        # Handle strings like "9.99999974737875E-06"
        return float(str(val).strip())
    except Exception:
        return None


def _extract_cwa(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    s = str(text)
    # Normalize underscores and spaces to single spaces so word boundaries work
    s_norm = re.sub(r"[_\s]+", " ", s)
    # Return only the code after "ASU-" (e.g., "1A01")
    # Handle forms: "CWA ASU - 1A01 - ...", "CWA_ASU-1A01_...", or just "ASU-1A01"
    m = re.search(r"\bCWA\b\s*ASU\s*-\s*([A-Za-z0-9]+)", s_norm, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"\bASU\s*-\s*([A-Za-z0-9]+)", s_norm, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _layer_key_from_record(rec: Dict[str, Any]) -> Optional[str]:
    return (
        rec.get("Item.Layer")
        or rec.get("General.Layer")
        or rec.get("Item.Name")
        or rec.get("General.Name")
        or rec.get("Element Name")
    )


def _collect_geometry(rec: Dict[str, Any]) -> Dict[str, Any]:
    # Pull only AutoCAD Geometry.* keys and coerce numbers where applicable
    # Output keys are without the "AutoCAD Geometry." prefix.
    # Exclude unwanted properties: Solid type, Rotation
    geom: Dict[str, Any] = {}
    for k, v in rec.items():
        if isinstance(k, str) and k.startswith(AUTO_GEOM_PREFIX):
            short = k[len(AUTO_GEOM_PREFIX) :]
            short_l = short.lower()
            # skip excluded properties (including numbered duplicates like "Solid type (2)")
            if short_l.startswith("solid type") or short_l.startswith("rotation"):
                continue
            # numeric coercion for common numeric fields
            if any(part in short_l for part in [
                "position x", "position y", "position z",
                "height", "length", "width"
            ]):
                geom[short] = _to_float(v)
            else:
                geom[short] = v
    return geom


def clean_data(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Separate by Category/Class
    layers: List[Dict[str, Any]] = [
        r for r in records if str(r.get("Category/Class", "")).strip().lower() == "layer"
    ]
    solids: List[Dict[str, Any]] = [
        r for r in records if str(r.get("Category/Class", "")).strip().lower() == "3d solid"
    ]

    # Normalization helper to make matching robust across underscores/spaces/case
    def _norm_key(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        t = str(s).strip().lower()
        # unify spaces to underscores, collapse multiple underscores
        t = re.sub(r"\s+", "_", t)
        t = re.sub(r"_+", "_", t)
        return t

    # Index solids by their normalized layer assignment to enable join
    solids_by_layer: Dict[str, List[Dict[str, Any]]] = {}
    for s in solids:
        key = _norm_key(_layer_key_from_record(s))
        if not key:
            continue
        solids_by_layer.setdefault(str(key), []).append(s)

    cleaned: List[Dict[str, Any]] = []

    for layer in layers:
        # Determine the best layer name key
        layer_name = _layer_key_from_record(layer)
        layer_name_norm = _norm_key(layer_name) or ""

        # Compute CWA
        cwa = _extract_cwa(layer_name) or _extract_cwa(layer.get("Element Name"))

        # Find matching solids and collect geometry (first match only to keep flat output)
        matched_solids = solids_by_layer.get(layer_name_norm, [])
        first_geom: Dict[str, Any] = {}
        for s in matched_solids:
            first_geom = _collect_geometry(s)
            if first_geom:
                break

        # Build output record with only requested fields
        out: Dict[str, Any] = {}
        # keep Element Name first
        if "Element Name" in layer:
            out["Element Name"] = layer.get("Element Name")
        # keep CWA (capitalized key)
        out["CWA"] = cwa
        # keep GUID from layer
        if "GUID" in layer:
            out["GUID"] = layer.get("GUID")
        # keep coordinates from layer if present
        for coord_key in ["X Coordinate", "Y Coordinate", "Z Coordinate"]:
            if coord_key in layer:
                out[coord_key] = _to_float(layer.get(coord_key))
        # attach flattened AutoCAD Geometry.* keys
        out.update(first_geom)
        # calculate Volume = Height * Length * Width when available
        h = first_geom.get("Height")
        l = first_geom.get("Length")
        w = first_geom.get("Width")
        if h is not None and l is not None and w is not None:
            try:
                out["Volume"] = float(h) * float(l) * float(w)
            except Exception:
                pass

        # Calculate bounding box: MinOfMinX/Y/Z and MaxOfMaxX/Y/Z
        # Use Position X/Y/Z as center, with Length/Width/Height as extents
        px = first_geom.get("Position X")
        py = first_geom.get("Position Y")
        pz = first_geom.get("Position Z")
        try:
            if px is not None and l is not None:
                half_l = float(l) / 2.0
                out["MinOfMinX"] = float(px) - half_l
                out["MaxOfMaxX"] = float(px) + half_l
            if py is not None and w is not None:
                half_w = float(w) / 2.0
                out["MinOfMinY"] = float(py) - half_w
                out["MaxOfMaxY"] = float(py) + half_w
            if pz is not None and h is not None:
                # Per requirement: Min Z = Z coordinate, Max Z = Z + Height
                out["MinOfMinZ"] = float(pz)
                out["MaxOfMaxZ"] = float(pz) + float(h)
        except Exception:
            # If any conversion fails, skip bbox for that axis
            pass

        cleaned.append(out)

    return cleaned
