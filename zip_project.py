# zip_project.py
import os
import zipfile
from pathlib import Path

def zip_project():
    project_dir = Path(__file__).parent.absolute()
    zip_filename = project_dir / "multi-source-rag.zip"
    
    print(f"Packaging project from: {project_dir}")
    print(f"Output ZIP file will be: {zip_filename}")
    
    # Exclude directories
    exclude_dirs = {
        ".git",
        "venv",
        ".venv",
        "__pycache__",
        "data",
        ".idea",
        ".vscode",
        "screenshots",
        "multi-source-rag.zip"
    }
    
    # Exclude extensions
    exclude_exts = {
        ".pyc",
        ".pyo",
        ".db",
        ".zip"
    }

    count = 0
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_dir):
            # Modify dirs in-place to skip excluded directories in recursion
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check exclusions
                if file_path.name in exclude_dirs:
                    continue
                if file_path.suffix in exclude_exts:
                    continue
                    
                # Calculate relative path to store in ZIP
                rel_path = file_path.relative_to(project_dir)
                
                print(f"  Adding: {rel_path}")
                zipf.write(file_path, rel_path)
                count += 1
                
    print(f"\nSuccess! Created {zip_filename.name} with {count} files.")
    print("You can download this zip file directly and update your GitHub repository.")

if __name__ == "__main__":
    zip_project()
