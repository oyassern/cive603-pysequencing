"""
MEI Dependency Rules Module

This module contains all dependency rules and helper functions for the MEI system.
It serves as the single source of truth for dependency logic and can be imported
by both the main logic module and the reporting module .

"""

import re
from typing import Tuple, Optional, List, Dict, Any


# -----------------------------
# Core Dependency Rules
# -----------------------------

# Special predecessor types that qualify for equipment and module activities
SPECIAL_PREDECESSOR_TYPES = {
    "Primary Steel": "Structure steel with special vertical dependency rules",
    "Concrete": "Concrete with specific vertical thresholds",
    "Pile Caps": "Pile caps with specific vertical thresholds", 
    "Concrete Pile Caps": "Concrete pile caps with specific vertical thresholds"
}

# Vertical dependency thresholds for different predecessor types
VERTICAL_THRESHOLDS = {
    "equipment": (0, 0.2),      # (threshold1, threshold2) for equipment predecessors
    "module": (0, 0.2),         # (threshold1, threshold2) for module predecessors
    "structure_steel": None,     # Special case: current_min_z between pred_min_z and pred_max_z
    "concrete": (0.5, 0.2),     # (threshold1, threshold2) for concrete predecessors
    "pile_cap": (0.5, 0.2),    # (threshold1, threshold2) for pile cap predecessors
    "concrete_pile_cap": (0.5, 0.2)  # (threshold1, threshold2) for concrete pile cap predecessors
}

# Horizontal overlap requirement (80%)
HORIZONTAL_OVERLAP_THRESHOLD = 0.8


# -----------------------------
# Helper Functions
# -----------------------------

def _simplify_for_rule_match(text: str) -> str:
    """
    Prepare an activity string for matching dependency 'keys'.
    
    Args:
        text: The text to simplify
        
    Returns:
        Simplified text with collapsed spaces
    """
    # Collapse spaces
    return re.sub(r'\s+', ' ', text.strip()).strip()


def contains_dependency(dep_word: str, activity_text: str, allowed_phrases: Optional[List[str]] = None) -> bool:
    """
    Match dependency keyword in activity text:
    - Finds dep_word anywhere
    - Rejects if followed by another descriptive word (qualifier) unless allowed
    - Ignores punctuation after dep_word
    
    Args:
        dep_word: The dependency keyword to search for
        activity_text: The activity text to search in
        allowed_phrases: List of allowed phrases that can follow the keyword
        
    Returns:
        True if dependency keyword is found and valid, False otherwise
    """
    if not dep_word or not activity_text:
        return False

    dep_word_clean = re.sub(r'\s+', ' ', dep_word.strip().lower())
    text_clean = re.sub(r'\s+', ' ', activity_text.strip().lower())

    idx = text_clean.find(dep_word_clean)
    while idx != -1:
        after = text_clean[idx + len(dep_word_clean):].strip()

        # If nothing after it → valid match
        if not after:
            return True

        # If next char is punctuation/comma/dash → valid match
        if after[0] in {",", "-", "–", "—", ";", ":"}:
            return True

        # Otherwise get the next token (word after dep_word)
        next_word = after.split()[0]
        combined = f"{dep_word_clean} {next_word}"

        # Allow only if explicitly in allowed_phrases
        if allowed_phrases and re.sub(r'\s+', ' ', combined.strip().lower()) in [re.sub(r'\s+', ' ', p.strip().lower()) for p in allowed_phrases]:
            return True

        # Not allowed → skip this occurrence
        idx = text_clean.find(dep_word_clean, idx + len(dep_word_clean))

    return False


def has_80_percent_area_overlap(box1: Tuple[float, float, float, float], 
                                box2: Tuple[float, float, float, float]) -> bool:
    """
    Calculate if two boxes have at least 80% area overlap.
    
    Args:
        box1: Tuple of (x_min, x_max, y_min, y_max) coordinates
        box2: Tuple of (x_min, x_max, y_min, y_max) coordinates
        
    Returns:
        True if either box has at least 80% overlap with the other
    """
    x_min1, x_max1, y_min1, y_max1 = box1
    x_min2, x_max2, y_min2, y_max2 = box2
    
    overlap_x = max(0, min(x_max1, x_max2) - max(x_min1, x_min2))
    overlap_y = max(0, min(y_max1, y_max2) - max(y_min1, y_min2))
    overlap_area = overlap_x * overlap_y
    
    area1 = (x_max1 - x_min1) * (y_max1 - y_min1)
    area2 = (x_max2 - x_min2) * (y_max2 - y_min2)
    
    percent1 = overlap_area / area1 if area1 > 0 else 0
    percent2 = overlap_area / area2 if area2 > 0 else 0
    
    return percent1 >= HORIZONTAL_OVERLAP_THRESHOLD or percent2 >= HORIZONTAL_OVERLAP_THRESHOLD


def has_vertical_dependency(predecessor_max_z: float, current_min_z: float, 
                           threshold1: float = 0, threshold2: float = 0.2) -> bool:
    """
    Check if the predecessor has a vertical dependency with the current activity.
    
    A vertical dependency exists if:
    current_min_z > (predecessor_max_z - threshold1) AND
    current_min_z < (predecessor_max_z + threshold2)
    
    Args:
        predecessor_max_z: Maximum Z coordinate of the predecessor activity
        current_min_z: Minimum Z coordinate of the current activity
        threshold1: Lower tolerance threshold (default: 0m)
        threshold2: Upper tolerance threshold (default: 0.2m)
        
    Returns:
        True if there is a vertical dependency, False otherwise
    """
    return (current_min_z > predecessor_max_z - threshold1) and (current_min_z < predecessor_max_z + threshold2)


# -----------------------------
# Rule Application Functions
# -----------------------------

def is_special_predecessor_type(predecessor_name: str, dependencies: Dict[str, List[str]]) -> Optional[str]:
    """
    Check if a predecessor qualifies as a special type for equipment/module activities.
    
    Args:
        predecessor_name: Name of the potential predecessor
        dependencies: Dictionary of dependency rules
        
    Returns:
        The dependency key if it's a special type, None otherwise
    """
    # Get dependency keys sorted by length (longest first for better matching)
    dep_keys = sorted(dependencies.keys(), key=len, reverse=True)
    
    # Check if predecessor matches any special type
    for dep_key in dep_keys:
        if contains_dependency(dep_key, predecessor_name, allowed_phrases=dependencies.get(dep_key, [])):
            if dep_key in SPECIAL_PREDECESSOR_TYPES:
                return dep_key
    
    return None


def check_equipment_predecessor_rules(predecessor: Dict[str, Any], current_activity: Dict[str, Any], 
                                    dependencies: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Check if a predecessor qualifies as a valid predecessor for an equipment activity.
    
    Args:
        predecessor: Dictionary containing predecessor activity data
        current_activity: Dictionary containing current activity data
        dependencies: Dictionary of dependency rules
        
    Returns:
        Dictionary with validation results and failure reasons
    """
    result = {
        "is_valid": False,
        "failure_reasons": [],
        "dependency_key": None
    }
    
    # Check if predecessor is equipment
    pred_is_equipment = bool(predecessor.get("TagNo"))
    
    if pred_is_equipment:
        # Equipment predecessor - use standard rules
        current_min_z = current_activity.get("MinOfMinZ", 0)
        pred_max_z = predecessor.get("MaxOfMaxZ", float('inf'))
        
        if not has_vertical_dependency(pred_max_z, current_min_z, *VERTICAL_THRESHOLDS["equipment"]):
            result["failure_reasons"].append("Vertical dependency check failed")
            return result
            
        # Check horizontal overlap
        if not _check_horizontal_overlap(current_activity, predecessor):
            result["failure_reasons"].append("Horizontal overlap check failed (< 80% overlap)")
            return result
            
        result["is_valid"] = True
        return result
    
    # Check if predecessor is a special type
    pred_key = is_special_predecessor_type(predecessor.get("ScheduleActivityID", ""), dependencies)
    result["dependency_key"] = pred_key
    
    if not pred_key:
        result["failure_reasons"].append("Not a qualifying predecessor type for equipment")
        return result
    
    # Apply special type rules
    if pred_key == "Primary Steel":
        if not _check_structure_steel_rules(predecessor, current_activity):
            result["failure_reasons"].append("Structure steel vertical dependency check failed")
            return result
    elif pred_key in ["Concrete", "Pile Caps", "Concrete Pile Caps"]:
        if not _check_concrete_pile_cap_rules(predecessor, current_activity, "equipment"):
            result["failure_reasons"].append("Concrete/pile cap vertical dependency check failed")
            return result
    else:
        result["failure_reasons"].append("Not a qualifying predecessor type for equipment")
        return result
    
    # Check horizontal overlap for special types
    if not _check_horizontal_overlap(current_activity, predecessor):
        result["failure_reasons"].append(f"{pred_key} horizontal overlap check failed")
        return result
    
    result["is_valid"] = True
    return result


def check_module_predecessor_rules(predecessor: Dict[str, Any], current_activity: Dict[str, Any], 
                                  dependencies: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Check if a predecessor qualifies as a valid predecessor for a module activity.
    
    Args:
        predecessor: Dictionary containing predecessor activity data
        current_activity: Dictionary containing current activity data
        dependencies: Dictionary of dependency rules
        
    Returns:
        Dictionary with validation results and failure reasons
    """
    result = {
        "is_valid": False,
        "failure_reasons": [],
        "dependency_key": None
    }
    
    # Check if predecessor is equipment or module
    pred_is_equipment = bool(predecessor.get("TagNo"))
    pred_is_module = bool(predecessor.get("ModuleNo"))
    
    if pred_is_equipment or pred_is_module:
        # Equipment or Module predecessor - use standard rules
        current_min_z = current_activity.get("MinOfMinZ", 0)
        pred_max_z = predecessor.get("MaxOfMaxZ", float('inf'))
        
        if not has_vertical_dependency(pred_max_z, current_min_z, *VERTICAL_THRESHOLDS["module"]):
            result["failure_reasons"].append("Vertical dependency check failed")
            return result
            
        # Check horizontal overlap
        if not _check_horizontal_overlap(current_activity, predecessor):
            result["failure_reasons"].append("Horizontal overlap check failed (< 80% overlap)")
            return result
            
        result["is_valid"] = True
        return result
    
    # Check if predecessor is a special type
    pred_key = is_special_predecessor_type(predecessor.get("ScheduleActivityID", ""), dependencies)
    result["dependency_key"] = pred_key
    
    if not pred_key:
        result["failure_reasons"].append("Not a qualifying predecessor type for modules")
        return result
    
    # Apply special type rules
    if pred_key == "Primary Steel":
        if not _check_structure_steel_rules(predecessor, current_activity):
            result["failure_reasons"].append("Structure steel vertical dependency check failed")
            return result
    elif pred_key in ["Concrete", "Pile Caps", "Concrete Pile Caps"]:
        if not _check_concrete_pile_cap_rules(predecessor, current_activity, "module"):
            result["failure_reasons"].append("Concrete/pile cap vertical dependency check failed")
            return result
    else:
        result["failure_reasons"].append("Not a qualifying predecessor type for modules")
        return result
    
    # Check horizontal overlap for special types
    if not _check_horizontal_overlap(current_activity, predecessor):
        result["failure_reasons"].append(f"{pred_key} horizontal overlap check failed")
        return result
    
    result["is_valid"] = True
    return result


def check_standard_predecessor_rules(predecessor: Dict[str, Any], current_activity: Dict[str, Any], 
                                    dependencies: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Check if a predecessor qualifies as a valid predecessor for a standard activity.
    
    Args:
        predecessor: Dictionary containing predecessor activity data
        current_activity: Dictionary containing current activity data
        dependencies: Dictionary of dependency rules
        
    Returns:
        Dictionary with validation results and failure reasons
    """
    result = {
        "is_valid": False,
        "failure_reasons": [],
        "dependency_key": None
    }
    
    # For standard activities, find dependency key by matching the CURRENT ACTIVITY name
    current_activity_name = current_activity.get("ScheduleActivityID", "")
    dep_keys = sorted(dependencies.keys(), key=len, reverse=True)
    
    dep_key = next((k for k in dep_keys if contains_dependency(k, _simplify_for_rule_match(current_activity_name), 
                                                               allowed_phrases=dependencies.get(k, []))), None)
    result["dependency_key"] = dep_key
    
    if not dep_key:
        result["failure_reasons"].append("No dependency key found for current activity")
        return result
    
    # Check if this predecessor matches the dependency rule
    preds = dependencies.get(dep_key, [])
    if not any(contains_dependency(pname, predecessor.get("ScheduleActivityID", ""), allowed_phrases=preds) for pname in preds):
        result["failure_reasons"].append("Dependency rule matching failed")
        return result
    
    result["is_valid"] = True
    return result


# -----------------------------
# Private Helper Functions
# -----------------------------

def _check_horizontal_overlap(current_activity: Dict[str, Any], predecessor: Dict[str, Any]) -> bool:
    """
    Check if two activities have sufficient horizontal overlap.
    
    Args:
        current_activity: Current activity data
        predecessor: Predecessor activity data
        
    Returns:
        True if horizontal overlap check passes, False otherwise
    """
    # Check if both activities have coordinates
    current_has_coords = all(col in current_activity for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
    pred_has_coords = all(col in predecessor for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
    
    if not current_has_coords:
        return False
    if not pred_has_coords:
        return False
    
    # Create bounding boxes
    current_box = (current_activity["MinOfMinX"], current_activity["MaxOfMaxX"], 
                   current_activity["MinOfMinY"], current_activity["MaxOfMaxY"])
    pred_box = (predecessor["MinOfMinX"], predecessor["MaxOfMaxX"], 
                predecessor["MinOfMinY"], predecessor["MaxOfMaxY"])
    
    return has_80_percent_area_overlap(current_box, pred_box)


def _check_structure_steel_rules(predecessor: Dict[str, Any], current_activity: Dict[str, Any]) -> bool:
    """
    Check structure steel vertical dependency rules.
    
    Args:
        predecessor: Predecessor activity data
        current_activity: Current activity data
        
    Returns:
        True if structure steel rules pass, False otherwise
    """
    current_min_z = current_activity.get("MinOfMinZ", 0)
    pred_min_z = predecessor.get("MinOfMinZ", float('-inf'))
    pred_max_z = predecessor.get("MaxOfMaxZ", float('inf'))
    
    # Check vertical dependency: Min Z of Current >= Min Z of Steel AND < Max Z of Steel
    return pred_min_z <= current_min_z < pred_max_z


def _check_concrete_pile_cap_rules(predecessor: Dict[str, Any], current_activity: Dict[str, Any], 
                                  activity_type: str) -> bool:
    """
    Check concrete/pile cap vertical dependency rules.
    
    Args:
        predecessor: Predecessor activity data
        current_activity: Current activity data
        activity_type: Type of current activity ("equipment" or "module")
        
    Returns:
        True if concrete/pile cap rules pass, False otherwise
    """
    current_min_z = current_activity.get("MinOfMinZ", 0)
    pred_max_z = predecessor.get("MaxOfMaxZ", float('inf'))
    
    if activity_type == "equipment":
        thresholds = VERTICAL_THRESHOLDS["concrete"]
    else:  # module
        thresholds = VERTICAL_THRESHOLDS["module"]
    
    return has_vertical_dependency(pred_max_z, current_min_z, *thresholds)
