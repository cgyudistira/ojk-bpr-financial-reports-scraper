"""
OJK BPR Konvensional Scraper - Main Entry Point Wrapper
"""
import sys
import subprocess
import os

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(root_dir, 'scripts', 'fetch_reports.py')
    
    # Forward all arguments to the actual script inside scripts/
    cmd = [sys.executable, script_path] + sys.argv[1:]
    
    # Execute the underlying script while preserving PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = root_dir
    
    try:
        result = subprocess.run(cmd, env=env, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\nScraping stopped by user.")
        sys.exit(1)

if __name__ == "__main__":
    main()
