"""
Database Utilities Module for MEI System

This module handles all database operations including loading dependency rules,
activities data, and discipline information. It provides a clean interface for
data access that can be used by both the main logic module and reporting modules.

Author: MEI System
Date: 2025
"""

import pyodbc
import pandas as pd
from typing import Tuple, Dict, List, Optional
import os


# -----------------------------
# Database Configuration
# -----------------------------

# Default database path - can be overridden
DEFAULT_DB_PATH = r"C:\Users\oyahmed\Desktop\oyahmed\PCL\AP MEI1\MEI1_ResearchDB (2).accdb"

# Database connection string template
CONNECTION_STRING_TEMPLATE = "DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={};"


# -----------------------------
# Database Connection Functions
# -----------------------------

def get_database_connection(db_path: Optional[str] = None) -> pyodbc.Connection:
    """
    Get a database connection to the MEI database.
    
    Args:
        db_path: Optional database path. If None, uses default path or environment variable.
        
    Returns:
        pyodbc.Connection: Database connection object
        
    Raises:
        Exception: If connection fails
    """
    if db_path is None:
        # Check environment variable first, then fall back to default
        db_path = os.environ.get('MEI_DB_PATH', DEFAULT_DB_PATH)
    
    connection_string = CONNECTION_STRING_TEMPLATE.format(db_path)
    
    try:
        conn = pyodbc.connect(connection_string)
        return conn
    except pyodbc.Error as e:
        raise Exception(f"Failed to connect to database at {db_path}: {str(e)}")


def test_database_connection(db_path: Optional[str] = None) -> bool:
    """
    Test if a database connection can be established.
    
    Args:
        db_path: Optional database path. If None, uses default path or environment variable.
        
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        conn = get_database_connection(db_path)
        conn.close()
        return True
    except Exception:
        return False


# -----------------------------
# Data Loading Functions
# -----------------------------

def load_dependency_rules(db_path: Optional[str] = None) -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, str]]:
    """
    Load dependency rules from the database.
    
    Args:
        db_path: Optional database path. If None, uses default path or environment variable.
        
    Returns:
        Tuple containing:
        - dependencies: Dictionary mapping successor names to allowed predecessor names
        - id_to_name: Dictionary mapping IDs to names
        - name_to_id: Dictionary mapping names to IDs
        
    Raises:
        Exception: If loading fails
    """
    try:
        conn = get_database_connection(db_path)
        
        # Load dependency rules - using correct table name from original
        deps_df = pd.read_sql(
            "SELECT * FROM dbo_SchedActivityDefaultPredecessors", conn
        ).dropna(how='all')
        
        # Load name mappings - using correct table name from original
        names_df = pd.read_sql(
            "SELECT ScheduleTaskID, ScheduleTaskShort FROM dbo_ScheduleTaskShort", conn
        ).dropna(how='all')
        
        conn.close()
        
        # Process name mappings
        id_to_name = dict(zip(names_df['ScheduleTaskID'], names_df['ScheduleTaskShort']))
        name_to_id = {name: id for id, name in id_to_name.items()}
        
        # Build dependency dict: successor_name -> [predecessor_names] - exactly as in original
        dependencies = {}
        for _, row in deps_df.iterrows():
            succ = id_to_name.get(row['ScheduleActivityID'])
            pred = id_to_name.get(row['PredScheduleActivityID'])
            if succ and pred:
                dependencies.setdefault(succ, [])
                if pred not in dependencies[succ]:
                    dependencies[succ].append(pred)
        
        return dependencies, id_to_name, name_to_id
        
    except Exception as e:
        raise Exception(f"Failed to load dependency rules: {str(e)}")


def load_activities_data(db_path: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Load activities data from the database.
    
    Args:
        db_path: Optional database path. If None, uses default path or environment variable.
        
    Returns:
        Tuple containing:
        - activities_df: DataFrame with activities data
        - full_name_to_id: Dictionary mapping full names to IDs
        
    Raises:
        Exception: If loading fails
    """
    try:
        conn = get_database_connection(db_path)
        
        # Load activities
        activities_df = pd.read_sql("SELECT * FROM dbo_ScheduleActivities", conn)
        
        # Load discipline information
        discipline_df = pd.read_sql("SELECT DisciplineID, Discipline FROM model_Discipline", conn)
        
        # Load name mappings for full names - using correct table name from original
        names_df = pd.read_sql(
            "SELECT ScheduleTaskID, ScheduleTaskShort FROM dbo_ScheduleTaskShort", conn
        ).dropna(how='all')
        
        conn.close()
        
        # Merge discipline information
        if 'DisciplineID' in activities_df.columns and not activities_df.empty:
            activities_df = activities_df.merge(discipline_df, on='DisciplineID', how='left')
        
        # Create full name to ID mapping - exactly as in original
        id_to_name = dict(zip(names_df['ScheduleTaskID'], names_df['ScheduleTaskShort']))
        full_name_to_id = {}
        
        # Sort short names by length in descending order to match longer names first
        sorted_id_to_name = sorted(id_to_name.items(), key=lambda x: len(x[1]), reverse=True)
        
        for _, activity_row in activities_df.iterrows():
            full_name = activity_row["ScheduleActivityID"]
            # Try to find a matching short name
            for task_id, short_name in sorted_id_to_name:
                if short_name in full_name:
                    full_name_to_id[full_name] = task_id
                    break
        
        return activities_df, full_name_to_id
        
    except Exception as e:
        raise Exception(f"Failed to load activities data: {str(e)}")


def load_schedule_dependencies_csv(csv_file_path: str = "schedule_dependencies.csv") -> pd.DataFrame:
    """
    Load the schedule dependencies CSV file.
    
    Args:
        csv_file_path: Path to the CSV file
        
    Returns:
        DataFrame containing the schedule dependencies
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        pd.errors.EmptyDataError: If CSV file is empty
    """
    try:
        df = pd.read_csv(csv_file_path)
        if df.empty:
            raise pd.errors.EmptyDataError("CSV file is empty")
        return df
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
    except pd.errors.EmptyDataError:
        raise
    except Exception as e:
        raise Exception(f"Error reading CSV file: {e}")


# -----------------------------
# Data Validation Functions
# -----------------------------

def validate_activities_data(activities_df: pd.DataFrame) -> List[str]:
    """
    Validate activities data for required columns and data quality.
    
    Args:
        activities_df: DataFrame containing activities data
        
    Returns:
        List of validation error messages (empty if validation passes)
    """
    errors = []
    
    # Check required columns
    required_columns = ["ScheduleActivityID", "CWA", "MinOfMinZ"]
    missing_columns = [col for col in required_columns if col not in activities_df.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {missing_columns}")
    
    # Check for empty CWA values
    if "CWA" in activities_df.columns:
        empty_cwa = activities_df["CWA"].isna().sum()
        if empty_cwa > 0:
            errors.append(f"Found {empty_cwa} activities with empty CWA values")
    
    # Check for duplicate activity IDs
    if "ScheduleActivityID" in activities_df.columns:
        duplicates = activities_df["ScheduleActivityID"].duplicated().sum()
        if duplicates > 0:
            errors.append(f"Found {duplicates} duplicate activity IDs")
    
    return errors


def validate_dependency_rules(dependencies: Dict[str, List[str]]) -> List[str]:
    """
    Validate dependency rules for data quality.
    
    Args:
        dependencies: Dictionary of dependency rules
        
    Returns:
        List of validation error messages (empty if validation passes)
    """
    errors = []
    
    if not dependencies:
        errors.append("No dependency rules found")
        return errors
    
    # Check for empty predecessor lists
    empty_preds = [succ for succ, preds in dependencies.items() if not preds]
    if empty_preds:
        errors.append(f"Found {len(empty_preds)} successors with empty predecessor lists")
    
    # Check for circular dependencies (basic check)
    for succ, preds in dependencies.items():
        if succ in preds:
            errors.append(f"Circular dependency detected: {succ} depends on itself")
    
    return errors


# -----------------------------
# Utility Functions
# -----------------------------

def get_activity_type(activity: pd.Series) -> str:
    """
    Determine the type of an activity based on its properties.
    
    Args:
        activity: Pandas Series containing activity data
        
    Returns:
        String indicating activity type: "Equipment", "Module", or "Standard"
    """
    if pd.notna(activity.get("TagNo")) and activity.get("TagNo") != "":
        return "Equipment"
    elif pd.notna(activity.get("ModuleNo")) and activity.get("ModuleNo") != "":
        return "Module"
    else:
        return "Standard"


def get_coordinate_status(activity: pd.Series) -> Dict[str, bool]:
    """
    Check if an activity has valid coordinate data.
    
    Args:
        activity: Pandas Series containing activity data
        
    Returns:
        Dictionary with coordinate status information
    """
    coord_columns = ["MinOfMinX", "MaxOfMaxX", "MinOfMinY", "MaxOfMaxY"]
    
    has_coordinates = all(col in activity for col in coord_columns)
    
    return {
        "has_coordinates": has_coordinates,
        "missing_columns": [col for col in coord_columns if col not in activity],
        "coordinate_columns": coord_columns
    }


def get_activities_by_cwa(activities_df: pd.DataFrame, cwa: str) -> pd.DataFrame:
    """
    Get all activities in a specific CWA.
    
    Args:
        activities_df: DataFrame containing all activities
        cwa: Construction Work Area identifier
        
    Returns:
        DataFrame containing activities in the specified CWA
    """
    if "CWA" not in activities_df.columns:
        raise ValueError("Activities DataFrame does not contain CWA column")
    
    return activities_df[activities_df["CWA"] == cwa].copy()


def get_unique_cwas(activities_df: pd.DataFrame) -> List[str]:
    """
    Get list of unique CWAs in the activities data.
    
    Args:
        activities_df: DataFrame containing activities data
        
    Returns:
        List of unique CWA identifiers
    """
    if "CWA" not in activities_df.columns:
        raise ValueError("Activities DataFrame does not contain CWA column")
    
    return activities_df["CWA"].dropna().unique().tolist()
