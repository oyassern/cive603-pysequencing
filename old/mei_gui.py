"""
MEI System GUI Application (Clean Version)

A modern, user-friendly interface for running the MEI dependency analysis system.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import sys
import subprocess


class MEIGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MEI System - Dependency Analysis")
        self.root.geometry("700x700")
        self.root.resizable(True, True)
        
        # Configure style
        self.setup_styles()
        
        # Variables
        self.database_path = tk.StringVar()
        self.create_logging = tk.BooleanVar(value=True)
        self.is_running = False
        
        # Progress tracking - clearer step descriptions
        self.progress_stages = [
            "Connecting to Database",
            "Generating Key Dictionary", 
            "Creating Activities Dependencies",
            "Creating Logging File"
        ]
        
        # Initialize widget references
        self.progress_items = []
        self.connection_status = None
        self.db_entry = None
        self.run_btn = None
        self.stop_btn = None
        self.status_text = None
        self.progress_frame = None
        
        # Create GUI elements
        self.create_widgets()
        
    def setup_styles(self):
        """Configure modern styling for the GUI"""
        style = ttk.Style()
        
        # Consistent font sizes and colors
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#1a1a1a")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 11), foreground="#333333")
        style.configure("Success.TLabel", font=("Segoe UI", 10, "bold"), foreground="#28a745")
        style.configure("Error.TLabel", font=("Segoe UI", 10, "bold"), foreground="#dc3545")
        
        # Button styles
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Secondary.TButton", font=("Segoe UI", 9))
        
        # Progress frame
        style.configure("Progress.TFrame", background="#f8f9fa")
        
    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="MEI System - Dependency Analysis", 
                               style="Title.TLabel")
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        # Database Selection Section
        self.create_database_section(main_frame)
        
        # Options Section
        self.create_options_section(main_frame)
        
        # Progress Section
        self.create_progress_section(main_frame)
        
        # Control Buttons
        self.create_control_buttons(main_frame)
        
        # Status Section
        self.create_status_section(main_frame)
        
    def create_database_section(self, parent):
        """Create database selection section"""
        # Section title
        db_title = ttk.Label(parent, text="Database Configuration", style="Subtitle.TLabel")
        db_title.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))
        
        # Database path label
        db_label = ttk.Label(parent, text="Database Path:", font=("Segoe UI", 10))
        db_label.grid(row=2, column=0, sticky=tk.W, padx=(0, 8))
        
        # Database path entry
        self.db_entry = ttk.Entry(parent, textvariable=self.database_path, width=50)
        self.db_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 8))
        
        # Browse button
        browse_btn = ttk.Button(parent, text="Browse", command=self.browse_database,
                               style="Secondary.TButton")
        browse_btn.grid(row=2, column=2)
        
        # Test connection button
        test_btn = ttk.Button(parent, text="Test Connection", command=self.test_connection,
                             style="Secondary.TButton")
        test_btn.grid(row=3, column=1, sticky=tk.W, pady=(4, 0))
        
        # Connection status
        self.connection_status = ttk.Label(parent, text="", style="Subtitle.TLabel")
        self.connection_status.grid(row=3, column=2, sticky=tk.W, pady=(4, 0))
        
    def create_options_section(self, parent):
        """Create options selection section"""
        # Section title
        options_title = ttk.Label(parent, text="Analysis Options", style="Subtitle.TLabel")
        options_title.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(15, 8))
        
        # Logging checkbox
        logging_check = ttk.Checkbutton(parent, text="Create Logging File", 
                                       variable=self.create_logging, 
                                       command=self.toggle_logging_option)
        logging_check.grid(row=5, column=0, columnspan=3, sticky=tk.W)
        
        # Logging description
        logging_desc = ttk.Label(parent, text="Generate detailed analysis report", 
                                style="Subtitle.TLabel")
        logging_desc.grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(2, 0))
        
    def create_progress_section(self, parent):
        """Create progress tracking section"""
        # Section title
        progress_title = ttk.Label(parent, text="Progress", style="Subtitle.TLabel")
        progress_title.grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(15, 8))
        
        # Progress frame
        self.progress_frame = ttk.Frame(parent, style="Progress.TFrame", padding="12")
        self.progress_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8))
        self.progress_frame.columnconfigure(1, weight=1)
        
        # Create progress items
        self.progress_items = []
        for i, stage in enumerate(self.progress_stages):
            self.create_progress_item(i, stage)
            
    def create_progress_item(self, index, stage_name):
        """Create a single progress item with better icons"""
        # Container frame
        item_frame = ttk.Frame(self.progress_frame)
        item_frame.grid(row=index, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=1)
        item_frame.columnconfigure(1, weight=1)
        
        # Progress indicator (better icons)
        spinner_label = ttk.Label(item_frame, text="○", font=("Segoe UI", 14))
        spinner_label.grid(row=0, column=0, padx=(0, 8))
        
        # Stage name
        stage_label = ttk.Label(item_frame, text=stage_name, style="Subtitle.TLabel")
        stage_label.grid(row=0, column=1, sticky=tk.W)
        
        # Progress item
        progress_item = {
            'frame': item_frame,
            'spinner': spinner_label,
            'stage': stage_label,
            'completed': False
        }
        self.progress_items.append(progress_item)
        
    def create_control_buttons(self, parent):
        """Create control buttons section"""
        # Button frame
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=9, column=0, columnspan=3, pady=15)
        
        # Run button
        self.run_btn = ttk.Button(button_frame, text="Run Analysis", 
                                 command=self.run_analysis, style="Primary.TButton")
        self.run_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # Stop button
        self.stop_btn = ttk.Button(button_frame, text="Stop", 
                                  command=self.stop_analysis, style="Secondary.TButton", 
                                  state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
    def create_status_section(self, parent):
        """Create status and output section"""
        # Section title
        status_title = ttk.Label(parent, text="Status & Output", style="Subtitle.TLabel")
        status_title.grid(row=10, column=0, columnspan=3, sticky=tk.W, pady=(15, 8))
        
        # Status text
        self.status_text = tk.Text(parent, height=6, width=70, wrap=tk.WORD, 
                                  font=("Consolas", 9))
        self.status_text.grid(row=11, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 8))
        
        # Scrollbar for status text
        status_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.status_text.yview)
        status_scrollbar.grid(row=11, column=3, sticky=(tk.N, tk.S))
        self.status_text.configure(yscrollcommand=status_scrollbar.set)
        
        # Configure row weights for status section
        parent.rowconfigure(11, weight=1)
        
    def browse_database(self):
        """Open file dialog to select database file"""
        file_path = filedialog.askopenfilename(
            title="Select Database File",
            filetypes=[("Access Database", "*.accdb"), ("All Files", "*.*")]
        )
        if file_path:
            self.database_path.set(file_path)
            self.log_status(f"Database selected: {file_path}")
            
    def test_connection(self):
        """Test database connection using subprocess"""
        db_path = self.database_path.get()
        if not db_path:
            messagebox.showerror("Error", "Please select a database file first.")
            return
            
        self.log_status("Testing database connection...")
        
        try:
            # Convert path to use forward slashes to avoid escape issues
            db_path_clean = db_path.replace('\\', '/')
            
            # Test connection by running a simple Python command
            test_script = f"""
import pyodbc
import sys
try:
    conn_str = "DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path_clean};"
    conn = pyodbc.connect(conn_str)
    conn.close()
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {{e}}")
    sys.exit(1)
"""
            
            result = subprocess.run([sys.executable, "-c", test_script], 
                                  capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0 and "SUCCESS" in result.stdout:
                self.connection_status.config(text="✓ Connected", foreground="#28a745")
                self.log_status("Database connection successful!")
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                self.connection_status.config(text="✗ Failed", foreground="#dc3545")
                self.log_status(f"Database connection failed: {error_msg}")
                
        except subprocess.TimeoutExpired:
            self.connection_status.config(text="✗ Timeout", foreground="#dc3545")
            self.log_status("Connection test timed out")
        except Exception as e:
            self.connection_status.config(text="✗ Error", foreground="#dc3545")
            self.log_status(f"Connection error: {str(e)}")
            
    def toggle_logging_option(self):
        """Handle logging option toggle"""
        if self.create_logging.get():
            self.log_status("Logging file will be generated")
        else:
            self.log_status("Logging file will not be generated")
            
    def run_analysis(self):
        """Run the complete analysis in a separate thread"""
        if self.is_running:
            return
            
        # Validate inputs
        if not self.database_path.get():
            messagebox.showerror("Error", "Please select a database file first.")
            return
            
        # Update UI state
        self.is_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Reset progress
        self.reset_progress()
        
        # Start analysis in separate thread
        self.analysis_thread = threading.Thread(target=self.run_analysis_thread)
        self.analysis_thread.daemon = True
        self.analysis_thread.start()
        
    def run_analysis_thread(self):
        """Run analysis in background thread using subprocess"""
        csv_file_path = None  # Store the CSV file path for logging
        try:
            # Stage 1: Connecting to Database
            self.update_progress(0, "Connecting to database...")
            time.sleep(0.5)
            self.complete_stage(0)
            
            # Stage 2: Generating Key Dictionary
            self.update_progress(1, "Generating key dictionary...")
            time.sleep(0.5)
            self.complete_stage(1)
            
            # Stage 3: Creating Activities Dependencies
            self.update_progress(2, "Creating activities dependencies...")
            self.log_status("Generating schedule dependencies CSV...")
            
            try:
                # Run the main analysis using subprocess with real-time output
                script_path = os.path.join(os.path.dirname(__file__), "meicoderev9_refactored.py")
                cmd = [sys.executable, script_path]
                env = os.environ.copy()
                env['MEI_DB_PATH'] = self.database_path.get()
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, env=env, cwd=os.path.dirname(__file__),
                                         bufsize=1, universal_newlines=True)
                
                # Capture output to extract CSV filename
                captured_stdout = ""
                
                # Read output in real-time
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        self.log_status(output.strip())
                        captured_stdout += output  # Capture for filename extraction
                
                # Read any remaining stderr output
                stderr_output = process.stderr.read()
                return_code = process.poll()
                
                if return_code == 0:
                    # Extract CSV filename from captured output
                    output_lines = captured_stdout.split('\n')
                    csv_file = None
                    for line in output_lines:
                        if "Schedule dependencies CSV generated:" in line:
                            csv_file = line.split(":")[-1].strip()
                            break
                    
                    if csv_file:
                        self.log_status(f"Schedule dependencies CSV generated: {csv_file}")
                        csv_file_path = csv_file  # Store for logging step
                        self.complete_stage(2)
                    else:
                        self.log_status("CSV generated but filename not found in output")
                        self.log_status(f"Full output: {captured_stdout}")
                        self.fail_stage(2)
                        return
                else:
                    self.log_status(f"Error generating dependencies: {stderr_output}")
                    self.log_status(f"Return code: {return_code}")
                    self.fail_stage(2)
                    return
                    
            except subprocess.TimeoutExpired:
                self.log_status("Analysis timed out after 120 seconds")
                self.fail_stage(2)
                return
            except Exception as e:
                self.log_status(f"Error generating dependencies: {str(e)}")
                self.fail_stage(2)
                return
                
            # Stage 4: Creating Logging File (if requested)
            if self.create_logging.get():
                self.update_progress(3, "Creating logging file...")
                self.log_status("Generating dependency analysis report...")
                
                try:
                    # Run the logger using subprocess with real-time output and CSV file path
                    script_path = os.path.join(os.path.dirname(__file__), "logger_refactored.py")
                    cmd = [sys.executable, script_path]
                    if csv_file_path:
                        cmd.append(csv_file_path)  # Pass CSV file path as argument
                    env = os.environ.copy()
                    env['MEI_DB_PATH'] = self.database_path.get()
                    
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, env=env, cwd=os.path.dirname(__file__),
                                             bufsize=1, universal_newlines=True)
                    
                    # Read output in real-time
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            self.log_status(output.strip())
                    
                    # Read any remaining stderr output
                    stderr_output = process.stderr.read()
                    return_code = process.poll()
                    
                    if return_code == 0:
                        self.log_status("Analysis report generated successfully")
                        self.complete_stage(3)
                    else:
                        self.log_status(f"Error generating report: {stderr_output}")
                        self.log_status(f"Return code: {return_code}")
                        self.fail_stage(3)
                        return
                        
                except subprocess.TimeoutExpired:
                    self.log_status("Report generation timed out after 120 seconds")
                    self.fail_stage(3)
                    return
                except Exception as e:
                    self.log_status(f"Error generating report: {str(e)}")
                    self.fail_stage(3)
                    return
            else:
                self.complete_stage(3)
                
            # Analysis complete
            self.log_status("Analysis completed successfully!")
            self.root.after(0, lambda: messagebox.showinfo("Success", "Analysis completed successfully!"))
            
        except Exception as e:
            self.log_status(f"Analysis failed: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {str(e)}"))
            
        finally:
            # Reset UI state
            self.root.after(0, self.analysis_complete)
            
    def stop_analysis(self):
        """Stop the running analysis"""
        if self.is_running:
            self.is_running = False
            self.log_status("Analysis stopped by user")
            self.analysis_complete()
            
    def analysis_complete(self):
        """Reset UI state after analysis completion"""
        self.is_running = False
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
    def update_progress(self, stage_index, message):
        """Update progress for a specific stage"""
        if stage_index < len(self.progress_items):
            self.root.after(0, lambda: self.log_status(message))
            
    def complete_stage(self, stage_index):
        """Mark a stage as completed"""
        if stage_index < len(self.progress_items):
            item = self.progress_items[stage_index]
            self.root.after(0, lambda: self.mark_stage_complete(item))
            
    def fail_stage(self, stage_index):
        """Mark a stage as failed"""
        if stage_index < len(self.progress_items):
            item = self.progress_items[stage_index]
            self.root.after(0, lambda: self.mark_stage_failed(item))
            
    def mark_stage_complete(self, item):
        """Mark a progress item as completed"""
        item['spinner'].config(text="✓", foreground="#28a745")
        item['completed'] = True
        
    def mark_stage_failed(self, item):
        """Mark a progress item as failed"""
        item['spinner'].config(text="✗", foreground="#dc3545")
        item['completed'] = False
        
    def reset_progress(self):
        """Reset all progress indicators"""
        for item in self.progress_items:
            item['spinner'].config(text="○", foreground="#6c757d")
            item['completed'] = False
            
    def log_status(self, message):
        """Add message to status log"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        self.root.after(0, lambda: self.add_to_status(log_message))
        
    def add_to_status(self, message):
        """Add message to status text widget"""
        self.status_text.insert(tk.END, message)
        self.status_text.see(tk.END)
        
        # Limit status text to last 800 characters
        if len(self.status_text.get("1.0", tk.END)) > 800:
            self.status_text.delete("1.0", "2.0")


def main():
    """Main entry point for the GUI application"""
    root = tk.Tk()
    app = MEIGUI(root)
    
    # Center the window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
    y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
    root.geometry(f"+{x}+{y}")
    
    # Start the GUI
    root.mainloop()


if __name__ == "__main__":
    main()
