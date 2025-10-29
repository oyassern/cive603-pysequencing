"""
MEI Code Rev9 - Main Logic Module (Refactored)

This module contains the main dependency logic for the MEI system.
It now imports rules and database functions from dedicated modules instead
of duplicating code, making it cleaner and more maintainable.

This module focuses solely on applying dependency logic to activities and
generating the schedule dependencies CSV file.

Author: MEI System
Date: 2025
"""

import pandas as pd
import os
from datetime import datetime

# Import from our new modules
from mei_rules import (
    check_equipment_predecessor_rules,
    check_module_predecessor_rules,
    check_standard_predecessor_rules,
    contains_dependency,
    _simplify_for_rule_match,
    has_80_percent_area_overlap,
    has_vertical_dependency
)
from db_utils import (
    load_dependency_rules,
    load_activities_data,
    get_activity_type,
    get_coordinate_status,
    get_activities_by_cwa
)


# -----------------------------
# Main Processing Functions
# -----------------------------

def process_activities(df: pd.DataFrame, dependencies: dict, id_to_name: dict, name_to_id: dict, full_name_to_id: dict) -> list:
    """
    Find predecessors for each activity within its CWA/SubArea group.
    
    This function processes activities and applies dependency rules to find valid predecessors.
    It handles three types of activities differently:
    - Equipment: Uses special rules for concrete, steel, pile caps, etc.
    - Module: Uses special rules similar to equipment
    - Standard: Uses standard dependency matching rules
    
    Args:
        df: DataFrame containing activities data
        dependencies: Dictionary of dependency rules
        id_to_name: Mapping from ID to name
        name_to_id: Mapping from name to ID
        full_name_to_id: Mapping from full name to ID
        
    Returns:
        List of dependency relationships found
    """
    df = df.copy()
    df["ScheduleActivityID"] = df["ScheduleActivityID"].astype(str)
    df["Rel"] = df.get("Rel", "FS")
    df["TaskType"] = df.get("TaskType", "Construct")
    df["Discipline"] = df.get("Discipline", "")

    df.sort_values(by=["CWA", "MinOfMinZ"], inplace=True)
    group_cols = ["CWA"] + (["SubArea"] if "SubArea" in df.columns else [])

    results = []
    dep_keys = sorted(dependencies.keys(), key=len, reverse=True)

    for _, group in df.groupby(group_cols):
        group = group.sort_values("MinOfMinZ").reset_index(drop=True)

        for _, act in group.iterrows():
            # Check if current activity is equipment (has TagNo)
            is_equipment = pd.notna(act.get("TagNo")) and act.get("TagNo") != ""
            # Check if current activity is module (has ModuleNo)
            is_module = pd.notna(act.get("ModuleNo")) and act.get("ModuleNo") != ""
            
            # Special equipment rule: If current activity is equipment, only follow special rules
            if is_equipment:
                current_min_z = act.get("MinOfMinZ", 0)
                # Create bounding box for current activity if coordinate columns exist
                has_coordinates = all(col in act for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                current_box = None
                if has_coordinates:
                    current_box = (act["MinOfMinX"], act["MaxOfMaxX"], act["MinOfMinY"], act["MaxOfMaxY"])
                
                # Check all other activities in the same group as potential predecessors
                for _, pred in group.iterrows():
                    # Skip if it's the same activity
                    if pred["ScheduleActivityID"] == act["ScheduleActivityID"]:
                        continue
                        
                    # Identify predecessor type using the same approach as default logic
                    pred_key = next((k for k in dep_keys if contains_dependency(k, _simplify_for_rule_match(pred["ScheduleActivityID"]), allowed_phrases=dependencies.get(k, []))), None)
                    
                    # Apply rules based on predecessor type
                    if pred_key:
                        # Check if predecessor is Equipment (has TagNo)
                        pred_is_equipment = pd.notna(pred.get("TagNo")) and pred.get("TagNo") != ""
                        
                        # Check if predecessor is Structure Steel
                        is_structure_steel = pred_key == "Primary Steel"
                        
                        # Check if predecessor is Concrete
                        is_concrete = pred_key == "Concrete"
                        
                        # Check if predecessor is Pile Cap
                        is_pile_cap = pred_key == "Pile Caps" or pred_key == "Concrete Pile Caps"
                        
                        # Check if predecessor is MCC, Switchgear, Transformer, or Substation
                        is_mcc = pred_key == "MCC"
                        is_switchgear = pred_key == "Switchgear"
                        is_transformer = pred_key == "Transformer"
                        is_substation = pred_key == "Substation"
                        
                        if pred_is_equipment:
                            # Equipment predecessor - use existing rules
                            pred_max_z = pred.get("MaxOfMaxZ", float('inf'))
                            if not has_vertical_dependency(pred_max_z, current_min_z, 0, 0.2):
                                continue
                                
                            # Check horizontal overlap - if coordinates are not available, this check fails
                            if has_coordinates:
                                has_coordinates_pred = all(col in pred for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                                if has_coordinates_pred:
                                    pred_box = (pred["MinOfMinX"], pred["MaxOfMaxX"], pred["MinOfMinY"], pred["MaxOfMaxY"])
                                    if not has_80_percent_area_overlap(current_box, pred_box):
                                        continue
                                else:
                                    # No coordinates for predecessor - horizontal check fails
                                    continue
                            else:
                                # No coordinates for current activity - horizontal check fails
                                continue
                                
                        elif is_structure_steel:
                            # Structure Steel predecessor
                            pred_min_z = pred.get("MinOfMinZ", float('-inf'))
                            pred_max_z = pred.get("MaxOfMaxZ", float('inf'))
                            
                            # Check vertical dependency: Min Z of Equipment >= Min Z of Steel AND < Max Z of Steel
                            if not (pred_min_z <= current_min_z < pred_max_z):
                                continue
                                
                            # Check horizontal overlap - if coordinates are not available, this check fails
                            if has_coordinates:
                                has_coordinates_pred = all(col in pred for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                                if has_coordinates_pred:
                                    pred_box = (pred["MinOfMinX"], pred["MaxOfMaxX"], pred["MinOfMinY"], pred["MaxOfMaxY"])
                                    if not has_80_percent_area_overlap(current_box, pred_box):
                                        continue
                                else:
                                    # No coordinates for predecessor - horizontal check fails
                                    continue
                            else:
                                # No coordinates for current activity - horizontal check fails
                                continue
                                        
                        elif is_concrete or is_pile_cap:
                            # Concrete or Pile Cap predecessor - use existing vertical and horizontal rules
                            pred_max_z = pred.get("MaxOfMaxZ", float('inf'))
                            if not has_vertical_dependency(pred_max_z, current_min_z, 0.5, 0.2):
                                continue
                                
                            # Check horizontal overlap - if coordinates are not available, this check fails
                            if has_coordinates:
                                has_coordinates_pred = all(col in pred for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                                if has_coordinates_pred:
                                    pred_box = (pred["MinOfMinX"], pred["MaxOfMaxX"], pred["MinOfMinY"], pred["MaxOfMaxY"])
                                    if not has_80_percent_area_overlap(current_box, pred_box):
                                        continue
                                else:
                                    # No coordinates for predecessor - horizontal check fails
                                    continue
                            else:
                                # No coordinates for current activity - horizontal check fails
                                continue
                        else:
                            # Skip other types of predecessors
                            continue
                    else:
                        # No pred_key found and not UG Conduit - skip this predecessor
                        continue
                    
                    # If we reach here, all conditions are met, add as predecessor
                    activity_id = full_name_to_id.get(act["ScheduleActivityID"], "")
                    predecessor_id = full_name_to_id.get(pred["ScheduleActivityID"], "")
                    
                    # Check if this dependency already exists to avoid duplicates
                    existing_dep = any(
                        r["ScheduleActivityID"] == act["ScheduleActivityID"] and
                        r["Predecessor"] == pred["ScheduleActivityID"]
                        for r in results
                    )
                    
                    if not existing_dep:
                        results.append({
                            "ScheduleActivityID": act["ScheduleActivityID"],
                            "ActivityScheduleTaskID": activity_id,
                            "Predecessor": pred["ScheduleActivityID"],
                            "PredecessorScheduleTaskID": predecessor_id,
                            "Rel": "FS",
                            "TaskType": "Construct",
                            "Discipline": act["Discipline"],
                        })
            # Special module rule: If current activity is module, only follow special rules
            elif is_module:
                current_min_z = act.get("MinOfMinZ", 0)
                # Create bounding box for current activity if coordinate columns exist
                has_coordinates = all(col in act for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                current_box = None
                if has_coordinates:
                    current_box = (act["MinOfMinX"], act["MaxOfMaxX"], act["MinOfMinY"], act["MaxOfMaxY"])
                
                # Check all other activities in the same group as potential predecessors
                for _, pred in group.iterrows():
                    # Skip if it's the same activity
                    if pred["ScheduleActivityID"] == act["ScheduleActivityID"]:
                        continue
                        
                    # Identify predecessor type using the same approach as default logic
                    pred_key = next((k for k in dep_keys if contains_dependency(k, _simplify_for_rule_match(pred["ScheduleActivityID"]), allowed_phrases=dependencies.get(k, []))), None)
                    
                    # Apply rules based on predecessor type
                    if pred_key:
                        # Check if predecessor is Equipment (has TagNo)
                        pred_is_equipment = pd.notna(pred.get("TagNo")) and pred.get("TagNo") != ""
                        
                        # Check if predecessor is Module (has ModuleNo)
                        pred_is_module = pd.notna(pred.get("ModuleNo")) and pred.get("ModuleNo") != ""
                        
                        # Check if predecessor is Structure Steel
                        is_structure_steel = pred_key == "Primary Steel"
                        
                        # Check if predecessor is Concrete
                        is_concrete = pred_key == "Concrete"
                        
                        # Check if predecessor is Pile Cap
                        is_pile_cap = pred_key == "Pile Caps" or pred_key == "Concrete Pile Caps"
                        
                        # Check if predecessor is MCC, Switchgear, Transformer, or Substation
                        is_mcc = pred_key == "MCC"
                        is_switchgear = pred_key == "Switchgear"
                        is_transformer = pred_key == "Transformer"
                        is_substation = pred_key == "Substation"
                        
                        if pred_is_equipment or pred_is_module:
                            # Equipment or Module predecessor - use existing rules
                            pred_max_z = pred.get("MaxOfMaxZ", float('inf'))
                            if not has_vertical_dependency(pred_max_z, current_min_z, 0, 0.2):
                                continue
                                
                            # Check horizontal overlap - if coordinates are not available, this check fails
                            if has_coordinates:
                                has_coordinates_pred = all(col in pred for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                                if has_coordinates_pred:
                                    pred_box = (pred["MinOfMinX"], pred["MaxOfMaxX"], pred["MinOfMinY"], pred["MaxOfMaxY"])
                                    if not has_80_percent_area_overlap(current_box, pred_box):
                                        continue
                                else:
                                    # No coordinates for predecessor - horizontal check fails
                                    continue
                            else:
                                # No coordinates for current activity - horizontal check fails
                                continue
                                
                        elif is_structure_steel:
                            # Structure Steel predecessor
                            pred_min_z = pred.get("MinOfMinZ", float('-inf'))
                            pred_max_z = pred.get("MaxOfMaxZ", float('inf'))
                            
                            # Check vertical dependency: Min Z of Module >= Min Z of Steel AND < Max Z of Steel
                            if not (pred_min_z <= current_min_z < pred_max_z):
                                continue
                                
                            # Check horizontal overlap - if coordinates are not available, this check fails
                            if has_coordinates:
                                has_coordinates_pred = all(col in pred for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                                if has_coordinates_pred:
                                    pred_box = (pred["MinOfMinX"], pred["MaxOfMaxX"], pred["MinOfMinY"], pred["MaxOfMaxY"])
                                    if not has_80_percent_area_overlap(current_box, pred_box):
                                        continue
                                else:
                                    # No coordinates for predecessor - horizontal check fails
                                    continue
                            else:
                                # No coordinates for current activity - horizontal check fails
                                continue
                                        
                        elif is_concrete or is_pile_cap:
                            # Concrete or Pile Cap predecessor - use existing vertical and horizontal rules
                            pred_max_z = pred.get("MaxOfMaxZ", float('inf'))
                            if not has_vertical_dependency(pred_max_z, current_min_z, 0, 0.2):
                                continue
                                
                            # Check horizontal overlap - if coordinates are not available, this check fails
                            if has_coordinates:
                                has_coordinates_pred = all(col in pred for col in ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"])
                                if has_coordinates_pred:
                                    pred_box = (pred["MinOfMinX"], pred["MaxOfMaxX"], pred["MinOfMinY"], pred["MaxOfMaxY"])
                                    if not has_80_percent_area_overlap(current_box, pred_box):
                                        continue
                                else:
                                    # No coordinates for predecessor - horizontal check fails
                                    continue
                            else:
                                # No coordinates for current activity - horizontal check fails
                                continue
                        else:
                            # Skip other types of predecessors
                            continue
                    else:
                        # No pred_key found - skip this predecessor
                        continue
                    
                    # If we reach here, all conditions are met, add as predecessor
                    activity_id = full_name_to_id.get(act["ScheduleActivityID"], "")
                    predecessor_id = full_name_to_id.get(pred["ScheduleActivityID"], "")
                    
                    # Check if this dependency already exists to avoid duplicates
                    existing_dep = any(
                        r["ScheduleActivityID"] == act["ScheduleActivityID"] and
                        r["Predecessor"] == pred["ScheduleActivityID"]
                        for r in results
                    )
                    
                    if not existing_dep:
                        results.append({
                            "ScheduleActivityID": act["ScheduleActivityID"],
                            "ActivityScheduleTaskID": activity_id,
                            "Predecessor": pred["ScheduleActivityID"],
                            "PredecessorScheduleTaskID": predecessor_id,
                            "Rel": "FS",
                            "TaskType": "Construct",
                            "Discipline": act["Discipline"],
                        })
            else:
                # Default dependency matching - EXACTLY as in original MEICodeRev9.py
                dep_key = next((k for k in dep_keys if contains_dependency(k, _simplify_for_rule_match(act["ScheduleActivityID"]), allowed_phrases=dependencies.get(k, []))), None)
                if dep_key:
                    preds = dependencies.get(dep_key, [])
                    matches = pd.DataFrame()
                    for pname in preds:
                        m = group[group['ScheduleActivityID'].apply(
                            lambda x: contains_dependency(pname, x, allowed_phrases=preds)
                        )]
                        matches = pd.concat([matches, m])
                    
                    matches.drop_duplicates(subset=['ScheduleActivityID'], inplace=True)
                    matches = matches[matches['ScheduleActivityID'] != act["ScheduleActivityID"]]
                    
                    for _, pred in matches.iterrows():
                        # Get ScheduleTaskID for activity and predecessor
                        activity_id = full_name_to_id.get(act["ScheduleActivityID"], "")
                        predecessor_id = full_name_to_id.get(pred["ScheduleActivityID"], "")
                        
                        results.append({
                            "ScheduleActivityID": act["ScheduleActivityID"],
                            "ActivityScheduleTaskID": activity_id,
                            "Predecessor": pred["ScheduleActivityID"],
                            "PredecessorScheduleTaskID": predecessor_id,
                            "Rel": "FS",
                            "TaskType": "Construct",
                            "Discipline": act["Discipline"],
                        })

    return results


def generate_schedule_dependencies_csv(output_file: str = None) -> str:
    """
    Generate the schedule dependencies CSV file by processing all activities.
    
    This is the main function that orchestrates the entire dependency analysis
    process by loading data, applying rules, and generating output.
    
    Args:
        output_file: Optional output file path. If None, generates timestamped filename.
        
    Returns:
        Path to the generated CSV file
        
    Raises:
        Exception: If any step in the process fails
    """
    try:
        # Load data from database
        print("Loading dependency rules and activities data...")
        dependencies, id_to_name, name_to_id = load_dependency_rules()
        activities_df, full_name_to_id = load_activities_data()
        
        # Process activities to find dependencies
        print("Processing activities and applying dependency rules...")
        results = process_activities(activities_df, dependencies, id_to_name, name_to_id, full_name_to_id)
        
        # Create DataFrame from dependency results
        pred_df = pd.DataFrame(results) if results else pd.DataFrame(columns=["ScheduleActivityID", "Predecessor", "Rel", "TaskType", "Discipline"])
        if not pred_df.empty:
            pred_df.drop_duplicates(inplace=True)

        # Ensure required columns before export - EXACTLY as in original MEICodeRev9.py
        for col, default in [("Rel", "FS"), ("TaskType", "Construct"), ("Discipline", "")]:
            if col not in activities_df.columns:
                activities_df[col] = default

        # Merge only on ScheduleActivityID to avoid KeyError - EXACTLY as in original
        export_df = activities_df[["ScheduleActivityID", "Rel", "TaskType"]].copy()
        export_df = export_df.merge(
            pred_df[["ScheduleActivityID", "Predecessor"]],
            on="ScheduleActivityID",
            how="left"
        )
        export_df["Predecessor"] = export_df["Predecessor"].fillna("")

        # Export without Discipline column - EXACTLY as in original
        # First, let's add the new ID columns to export_df
        export_df["ActivityScheduleTaskID"] = ""
        export_df["PredecessorScheduleTaskID"] = ""
        
        # Fill in the ID values where we have matches
        for idx, row in export_df.iterrows():
            if row["ScheduleActivityID"] in full_name_to_id:
                export_df.at[idx, "ActivityScheduleTaskID"] = full_name_to_id[row["ScheduleActivityID"]]
            if row["Predecessor"] in full_name_to_id:
                export_df.at[idx, "PredecessorScheduleTaskID"] = full_name_to_id[row["Predecessor"]]
        
        # Generate output filename if not provided
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"schedule_dependencies_{timestamp}.csv"
        
        # Export with exact same column order as original
        export_df[["ScheduleActivityID", "ActivityScheduleTaskID", "Rel", "TaskType", "Predecessor", "PredecessorScheduleTaskID"]].to_csv(
            output_file, index=False
        )
        print(f"Schedule dependencies CSV generated: {output_file}")
        print(f"Total dependency relationships found: {len(pred_df)}")
        
        return output_file
        
    except Exception as e:
        print(f"Error generating schedule dependencies: {e}")
        raise


# -----------------------------
# Utility Functions
# -----------------------------

def get_dependency_summary(csv_file: str) -> dict:
    """
    Generate a summary of the dependency analysis results.
    
    Args:
        csv_file: Path to the generated CSV file
        
    Returns:
        Dictionary containing summary statistics
    """
    try:
        df = pd.read_csv(csv_file)
        
        summary = {
            "total_activities": len(df),
            "activities_with_predecessors": len(df[df["Predecessor"].notna()]),
            "activities_without_predecessors": len(df[df["Predecessor"].isna()]),
            "activity_types": df["ActivityType"].value_counts().to_dict() if "ActivityType" in df.columns else {},
            "cwa_distribution": df["CWA"].value_counts().to_dict() if "CWA" in df.columns else {},
            "dependency_keys": df["DependencyKey"].value_counts().to_dict() if "DependencyKey" in df.columns else {}
        }
        
        return summary
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return {}


# -----------------------------
# Main Execution
# -----------------------------

if __name__ == "__main__":
    """
    Main execution block for the MEI dependency analysis.
    
    This runs when the script is executed directly and generates
    the schedule dependencies CSV file.
    """
    try:
        # Generate the CSV file
        csv_file = generate_schedule_dependencies_csv()
        
        # Generate and display summary
        summary = get_dependency_summary(csv_file)
        
        print("\n" + "="*50)
        print("DEPENDENCY ANALYSIS SUMMARY")
        print("="*50)
        print(f"Total activities processed: {summary.get('total_activities', 0)}")
        print(f"Activities with predecessors: {summary.get('activities_with_predecessors', 0)}")
        print(f"Activities without predecessors: {summary.get('activities_without_predecessors', 0)}")
        
        if summary.get('activity_types'):
            print(f"\nActivity type distribution:")
            for activity_type, count in summary['activity_types'].items():
                print(f"  {activity_type}: {count}")
        
        print(f"\nAnalysis complete! Check the CSV file: {csv_file}")
        
    except Exception as e:
        print(f"Fatal error during execution: {e}")
        import traceback
        traceback.print_exc()
