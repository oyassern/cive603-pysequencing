"""
MEI Dependency Logger - Reporting Module (Refactored)

This module generates comprehensive reports analyzing activities without predecessors.
It now imports rules and database functions from dedicated modules instead of
duplicating code, making it cleaner and more maintainable.

This module focuses solely on report generation (CSV export, logging messages)
and calls the logic functions but does not re-implement them.


"""

import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any

# Import from our new modules
from mei_rules import (
    check_equipment_predecessor_rules,
    check_module_predecessor_rules,
    check_standard_predecessor_rules
)
from db_utils import (
    load_dependency_rules,
    load_activities_data,
    load_schedule_dependencies_csv,
    get_activity_type,
    get_coordinate_status,
    get_activities_by_cwa
)


# -----------------------------
# Analysis Functions
# -----------------------------

def identify_activities_without_predecessors(dependencies_df: pd.DataFrame) -> List[str]:
    """
    Identify all activities that have no predecessors.
    
    Args:
        dependencies_df: DataFrame containing schedule dependencies
        
    Returns:
        List of activity IDs that have no predecessors
    """
    activities_without_preds = []
    
    # Group by activity to see which ones have no predecessors
    activity_groups = dependencies_df.groupby('ScheduleActivityID')
    
    for activity_id, group in activity_groups:
        # Check if this activity has any non-empty predecessors
        has_predecessors = group['Predecessor'].notna().any() and group['Predecessor'].str.strip().ne('').any()
        
        if not has_predecessors:
            activities_without_preds.append(activity_id)
    
    return activities_without_preds


def analyze_why_no_predecessor(activity_id: str, activities_df: pd.DataFrame, 
                               dependencies: Dict[str, List[str]], 
                               full_name_to_id: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Analyze why an activity has no predecessor by following the exact logic from mei_rules.py.
    
    This function uses the rule checking functions from mei_rules.py to determine
    why each potential predecessor failed to qualify as a dependency.
    
    Args:
        activity_id: ID of the activity to analyze
        activities_df: DataFrame containing all activities data
        dependencies: Dictionary of dependency rules
        full_name_to_id: Mapping from full activity names to ScheduleTaskID
        
    Returns:
        List of potential predecessors with detailed failure reasons
    """
    analysis_results = []
    
    # Get the activity row
    activity_row = activities_df[activities_df['ScheduleActivityID'] == activity_id]
    if activity_row.empty:
        return [{"error": f"Activity {activity_id} not found in activities data"}]
    
    activity = activity_row.iloc[0]
    
    # Get activities in the same CWA
    cwa = activity.get('CWA', '')
    if not cwa:
        return [{"error": f"Activity {activity_id} has no CWA information"}]
    
    group = get_activities_by_cwa(activities_df, cwa)
    
    # Determine current activity type
    current_activity_type = get_activity_type(activity)
    
    # Check all other activities in the same group as potential predecessors
    for _, pred in group.iterrows():
        # Skip if it's the same activity
        if pred["ScheduleActivityID"] == activity_id:
            continue
        
        # Prepare analysis result structure
        pred_analysis = {
            "predecessor_id": pred["ScheduleActivityID"],
            "predecessor_name": pred["ScheduleActivityID"],
            "dependency_key": None,
            "failure_reasons": [],
            "coordinate_info": {},
            "activity_type": current_activity_type,
            "predecessor_type": get_activity_type(pred)
        }
        
        # Get coordinate information
        current_coord_status = get_coordinate_status(activity)
        pred_coord_status = get_coordinate_status(pred)
        
        pred_analysis["coordinate_info"] = {
            "pred_has_coordinates": pred_coord_status["has_coordinates"],
            "current_has_coordinates": current_coord_status["has_coordinates"],
            "pred_max_z": pred.get("MaxOfMaxZ", float('inf')),
            "pred_min_z": pred.get("MinOfMinZ", float('-inf')),
            "current_min_z": activity.get("MinOfMinZ", 0)
        }
        
        # Apply the appropriate rule checking function based on current activity type
        if current_activity_type == "Equipment":
            rule_result = check_equipment_predecessor_rules(pred, activity, dependencies)
        elif current_activity_type == "Module":
            rule_result = check_module_predecessor_rules(pred, activity, dependencies)
        else:  # Standard
            rule_result = check_standard_predecessor_rules(pred, activity, dependencies)
        
        # Extract results from rule checking
        pred_analysis["dependency_key"] = rule_result.get("dependency_key")
        pred_analysis["failure_reasons"] = rule_result.get("failure_reasons", [])
        
        analysis_results.append(pred_analysis)
    
    return analysis_results


# -----------------------------
# Report Generation Functions
# -----------------------------

def generate_dependency_analysis_csv(csv_file_path: str = "schedule_dependencies.csv") -> str:
    """
    Generate a comprehensive CSV report analyzing activities without predecessors.
    
    This function loads data, identifies activities without predecessors, and
    analyzes why each potential predecessor failed to qualify using the rules
    from mei_rules.py.
    
    Args:
        csv_file_path: Path to the schedule dependencies CSV file
        
    Returns:
        Path to the generated analysis CSV report
        
    Raises:
        Exception: If any step in the analysis fails
    """
    try:
        # Load data
        print("Loading dependency rules and activities data...")
        dependencies, id_to_name, name_to_id = load_dependency_rules()
        activities_df, full_name_to_id = load_activities_data()
        
        # Load the CSV file
        print(f"Loading CSV file: {csv_file_path}")
        if not os.path.exists(csv_file_path):
            print(f"Error: CSV file {csv_file_path} not found!")
            return None
        
        dependencies_df = load_schedule_dependencies_csv(csv_file_path)
        
        # Identify activities without predecessors
        print("Identifying activities without predecessors...")
        activities_without_preds = identify_activities_without_predecessors(dependencies_df)
        
        # Generate CSV report
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        csv_filename = f"dependency_analysis_report_{timestamp}.csv"
        
        # Prepare data for CSV
        csv_rows = []
        
        for activity_id in activities_without_preds:
            # Get activity details
            activity_row = activities_df[activities_df['ScheduleActivityID'] == activity_id]
            if activity_row.empty:
                continue
                
            activity = activity_row.iloc[0]
            
            # Analyze potential predecessors
            potential_preds = analyze_why_no_predecessor(activity_id, activities_df, dependencies, full_name_to_id)
            
            if not potential_preds:
                # No potential predecessors found
                csv_rows.append({
                    "Activity_ID": activity_id,
                    "Activity_Type": "Unknown",
                    "CWA": activity.get('CWA', 'N/A'),
                    "Discipline": activity.get('Discipline', 'N/A'),
                    "Z_Coordinate": activity.get('MinOfMinZ', 'N/A'),
                    "Has_Coordinates": get_coordinate_status(activity)["has_coordinates"],
                    "Predecessor_ID": "N/A",
                    "Predecessor_Type": "N/A",
                    "Dependency_Key": "N/A",
                    "Failure_Reasons": "No potential predecessors found in same CWA",
                    "Pred_Coordinates": "N/A",
                    "Current_Coordinates": "N/A",
                    "Pred_Max_Z": "N/A",
                    "Pred_Min_Z": "N/A",
                    "Current_Min_Z": "N/A"
                })
            else:
                # Add each potential predecessor analysis
                for pred_analysis in potential_preds:
                    if "error" in pred_analysis:
                        csv_rows.append({
                            "Activity_ID": activity_id,
                            "Activity_Type": "Unknown",
                            "CWA": activity.get('CWA', 'N/A'),
                            "Discipline": activity.get('Discipline', 'N/A'),
                            "Z_Coordinate": activity.get('MinOfMinZ', 'N/A'),
                            "Has_Coordinates": get_coordinate_status(activity)["has_coordinates"],
                            "Predecessor_ID": "N/A",
                            "Predecessor_Type": "N/A",
                            "Dependency_Key": "N/A",
                            "Failure_Reasons": pred_analysis["error"],
                            "Pred_Coordinates": "N/A",
                            "Current_Coordinates": "N/A",
                            "Pred_Max_Z": "N/A",
                            "Pred_Min_Z": "N/A",
                            "Current_Min_Z": "N/A"
                        })
                    else:
                        coord_info = pred_analysis["coordinate_info"]
                        csv_rows.append({
                            "Activity_ID": activity_id,
                            "Activity_Type": pred_analysis["activity_type"],
                            "CWA": activity.get('CWA', 'N/A'),
                            "Discipline": activity.get('Discipline', 'N/A'),
                            "Z_Coordinate": activity.get('MinOfMinZ', 'N/A'),
                            "Has_Coordinates": get_coordinate_status(activity)["has_coordinates"],
                            "Predecessor_ID": pred_analysis["predecessor_id"],
                            "Predecessor_Type": pred_analysis["predecessor_type"],
                            "Dependency_Key": pred_analysis["dependency_key"] or "None",
                            "Failure_Reasons": "; ".join(pred_analysis["failure_reasons"]) if pred_analysis["failure_reasons"] else "All rules passed (should be predecessor)",
                            "Pred_Coordinates": coord_info["pred_has_coordinates"],
                            "Current_Coordinates": coord_info["current_has_coordinates"],
                            "Pred_Max_Z": coord_info["pred_max_z"],
                            "Pred_Min_Z": coord_info["pred_min_z"],
                            "Current_Min_Z": coord_info["current_min_z"]
                        })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(csv_rows)
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        
        print(f"CSV report generated: {csv_filename}")
        print(f"Total rows: {len(df)}")
        print(f"Activities without predecessors: {len(activities_without_preds)}")
        
        return csv_filename
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        raise


def generate_analysis_summary(csv_file: str) -> Dict[str, Any]:
    """
    Generate a summary of the dependency analysis results.
    
    Args:
        csv_file: Path to the analysis CSV file
        
    Returns:
        Dictionary containing summary statistics and insights
    """
    try:
        df = pd.read_csv(csv_file)
        
        # Basic statistics
        summary = {
            "total_rows": len(df),
            "unique_activities": df['Activity_ID'].nunique(),
            "activities_without_predecessors": df['Activity_ID'].nunique(),
            "activity_types": df['Activity_Type'].value_counts().to_dict() if 'Activity_Type' in df.columns else {},
            "failure_reasons": df['Failure_Reasons'].value_counts().to_dict() if 'Failure_Reasons' in df.columns else {}
        }
        
        # Top failure reasons
        if 'Failure_Reasons' in df.columns:
            top_failures = df['Failure_Reasons'].value_counts().head(5)
            summary["top_failure_reasons"] = {reason: count for reason, count in top_failures.items()}
        
        return summary
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return {}


# -----------------------------
# Main Execution
# -----------------------------

if __name__ == "__main__":
    """
    Main execution block for the dependency logger.
    
    This runs when the script is executed directly and generates
    the dependency analysis CSV report.
    
    Usage: python logger_refactored.py [csv_file_path]
    If csv_file_path is not provided, it defaults to "schedule_dependencies.csv"
    """
    import sys
    
    # Get CSV file path from command line argument or use default
    csv_file_path = "schedule_dependencies.csv"
    if len(sys.argv) > 1:
        csv_file_path = sys.argv[1]
    
    try:
        # Generate the CSV report
        csv_file = generate_dependency_analysis_csv(csv_file_path)
        
        if csv_file:
            # Generate and display summary
            summary = generate_analysis_summary(csv_file)
            
            print("\n" + "="*50)
            print("DEPENDENCY ANALYSIS SUMMARY")
            print("="*50)
            print(f"Total rows: {summary.get('total_rows', 0)}")
            print(f"Unique activities: {summary.get('unique_activities', 0)}")
            print(f"Activities without predecessors: {summary.get('activities_without_predecessors', 0)}")
            
            if summary.get('activity_types'):
                print(f"\nActivity Types:")
                for activity_type, count in summary['activity_types'].items():
                    print(f"  {activity_type}: {count}")
            
            if summary.get('top_failure_reasons'):
                print(f"\nTop 5 Failure Reasons:")
                for reason, count in summary['top_failure_reasons'].items():
                    print(f"  {reason}: {count}")
            
            print(f"\nAnalysis complete! Check the CSV report: {csv_file}")
        else:
            print("Failed to generate CSV report")
            
    except Exception as e:
        print(f"Fatal error during execution: {e}")
        import traceback
        traceback.print_exc()
