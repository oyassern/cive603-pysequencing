"""
MEI Combined Demo - Entry Point Script

This script demonstrates how to use both the main logic module (meicoderev9_refactored.py)
and the reporting module (logger_refactored.py) together in a clean, modular way.

It shows the complete workflow:
1. Generate schedule dependencies using the main logic
2. Analyze activities without predecessors using the reporting module
3. Display  results


"""

import os
import sys
from datetime import datetime

# Import our refactored modules
from meicoderev9_refactored import generate_schedule_dependencies_csv, get_dependency_summary
from logger_refactored import generate_dependency_analysis_csv, generate_analysis_summary


# -----------------------------
# Main Workflow Functions
# -----------------------------

def run_complete_workflow(output_dir: str = None) -> dict:
    """
    Run the complete MEI dependency analysis workflow.
    
    This function demonstrates the full pipeline:
    1. Generate schedule dependencies CSV
    2. Analyze activities without predecessors
    3. Generate comprehensive reports
    
    Args:
        output_dir: Optional directory for output files. If None, uses current directory.
        
    Returns:
        Dictionary containing workflow results and file paths
    """
    print("=" * 60)
    print("MEI DEPENDENCY ANALYSIS - COMPLETE WORKFLOW")
    print("=" * 60)
    
    workflow_results = {
        "start_time": datetime.now(),
        "dependencies_csv": None,
        "analysis_csv": None,
        "dependencies_summary": {},
        "analysis_summary": {},
        "success": False
    }
    
    try:
        # Step 1: Generate schedule dependencies CSV
        print("\nStep 1: Generating schedule dependencies CSV...")
        print("-" * 40)
        
        dependencies_csv = generate_schedule_dependencies_csv()
        if dependencies_csv:
            workflow_results["dependencies_csv"] = dependencies_csv
            print(f"✓ Dependencies CSV generated: {dependencies_csv}")
            
            # Generate summary of dependencies
            dependencies_summary = get_dependency_summary(dependencies_csv)
            workflow_results["dependencies_summary"] = dependencies_summary
            
            print(f"  - Total activities: {dependencies_summary.get('total_activities', 0)}")
            print(f"  - Activities with predecessors: {dependencies_summary.get('activities_with_predecessors', 0)}")
            print(f"  - Activities without predecessors: {dependencies_summary.get('activities_without_predecessors', 0)}")
        else:
            print("✗ Failed to generate dependencies CSV")
            return workflow_results
        
        # Step 2: Analyze activities without predecessors
        print("\nStep 2: Analyzing activities without predecessors...")
        print("-" * 40)
        
        analysis_csv = generate_dependency_analysis_csv(dependencies_csv)
        if analysis_csv:
            workflow_results["analysis_csv"] = analysis_csv
            print(f"✓ Analysis CSV generated: {analysis_csv}")
            
            # Generate summary of analysis
            analysis_summary = generate_analysis_summary(analysis_csv)
            workflow_results["analysis_summary"] = analysis_summary
            
            print(f"  - Total analysis rows: {analysis_summary.get('total_rows', 0)}")
            print(f"  - Unique activities analyzed: {analysis_summary.get('unique_activities', 0)}")
            
            # Top failure reasons display removed as requested
        else:
            print("✗ Failed to generate analysis CSV")
            return workflow_results
        
        # Step 3: Workflow complete
        workflow_results["success"] = True
        workflow_results["end_time"] = datetime.now()
        
        print("\n" + "=" * 60)
        print("WORKFLOW COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        return workflow_results
        
    except Exception as e:
        print(f"\n✗ Workflow failed with error: {e}")
        import traceback
        traceback.print_exc()
        return workflow_results


def display_workflow_results(results: dict):
    """
    Display comprehensive results from the workflow.
    
    Args:
        results: Dictionary containing workflow results
    """
    if not results.get("success"):
        print("Cannot display results - workflow was not successful")
        return
    
    print("\n" + "=" * 60)
    print("WORKFLOW RESULTS SUMMARY")
    print("=" * 60)
    
    # Timing information
    start_time = results.get("start_time")
    end_time = results.get("end_time")
    if start_time and end_time:
        duration = end_time - start_time
        print(f"Total execution time: {duration}")
    
    # File information
    print(f"\nGenerated Files:")
    print(f"  • Dependencies CSV: {results.get('dependencies_csv', 'N/A')}")
    print(f"  • Analysis CSV: {results.get('analysis_csv', 'N/A')}")
    
    # Dependencies summary
    deps_summary = results.get("dependencies_summary", {})
    if deps_summary:
        print(f"\nDependencies Summary:")
        print(f"  • Total activities processed: {deps_summary.get('total_activities', 0)}")
        print(f"  • Activities with predecessors: {deps_summary.get('activities_with_predecessors', 0)}")
        print(f"  • Activities without predecessors: {deps_summary.get('activities_without_predecessors', 0)}")
        
        if deps_summary.get('activity_types'):
            print(f"  • Activity type distribution:")
            for activity_type, count in deps_summary['activity_types'].items():
                print(f"    - {activity_type}: {count}")
    
    # Analysis summary
    analysis_summary = results.get("analysis_summary", {})
    if analysis_summary:
        print(f"\nAnalysis Summary:")
        print(f"  • Total analysis rows: {analysis_summary.get('total_rows', 0)}")
        print(f"  • Unique activities analyzed: {analysis_summary.get('unique_activities', 0)}")
        
        if analysis_summary.get('activity_types'):
            print(f"  • Activity types in analysis:")
            for activity_type, count in analysis_summary['activity_types'].items():
                print(f"    - {activity_type}: {count}")
        
        # Top failure reasons display removed as requested


def run_individual_modules():
    """
    Demonstrate running individual modules separately.
    
    This shows how the modular architecture allows you to use
    each component independently.
    """
    print("\n" + "=" * 60)
    print("INDIVIDUAL MODULE DEMONSTRATION")
    print("=" * 60)
    
    print("\n1. Testing database connection...")
    try:
        from db_utils import test_database_connection
        if test_database_connection():
            print("✓ Database connection successful")
        else:
            print("✗ Database connection failed")
    except Exception as e:
        print(f"✗ Database connection test failed: {e}")
    
    print("\n2. Testing rules module...")
    try:
        from mei_rules import SPECIAL_PREDECESSOR_TYPES, VERTICAL_THRESHOLDS
        print(f"✓ Rules module loaded successfully")
        print(f"  - Special predecessor types: {len(SPECIAL_PREDECESSOR_TYPES)}")
        print(f"  - Vertical thresholds: {len(VERTICAL_THRESHOLDS)}")
    except Exception as e:
        print(f"✗ Rules module test failed: {e}")
    
    print("\n3. Testing utility functions...")
    try:
        from db_utils import get_activity_type
        test_activity = {"TagNo": "TEST123", "ModuleNo": None}
        activity_type = get_activity_type(test_activity)
        print(f"✓ Utility functions working - Activity type: {activity_type}")
    except Exception as e:
        print(f"✗ Utility functions test failed: {e}")


# -----------------------------
# Main Execution
# -----------------------------

if __name__ == "__main__":
    """
    Main execution block for the MEI combined demo.
    
    This demonstrates the complete workflow and shows how the
    modular architecture works together.
    """
    print("MEI Combined Demo - Modular Architecture Demonstration")
    print("This script shows how the refactored modules work together")
    
    try:
        # Run individual module tests first
        run_individual_modules()
        
        # Ask user if they want to run the complete workflow
        print("\n" + "=" * 60)
        response = input("Do you want to run the complete workflow? (y/n): ").lower().strip()
        
        if response in ['y', 'yes']:
            # Run the complete workflow
            results = run_complete_workflow()
            
            # Display results
            display_workflow_results(results)
            
            print("\n" + "=" * 60)
            print("DEMO COMPLETE!")
            print("=" * 60)
            print("The refactored architecture provides:")
            print("✓ Clean separation of concerns")
            print("✓ No code duplication")
            print("✓ Easy maintenance and extension")
            print("✓ Modular design for future enhancements")
            
        else:
            print("Demo completed without running full workflow.")
            print("You can run individual modules as needed.")
            
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
