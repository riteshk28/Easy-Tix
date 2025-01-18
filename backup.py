import shutil
from datetime import datetime
import os

def create_backup():
    # Create backups directory if it doesn't exist
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    # Create timestamp for backup name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'backups/backup_{timestamp}'
    
    # Create backup
    shutil.copytree('.', backup_dir, ignore=shutil.ignore_patterns(
        'backups*', '__pycache__*', '*.pyc', 'venv*', '.git*'
    ))
    
    print(f"Backup created: {backup_dir}")
    return backup_dir

def restore_backup(backup_dir):
    """Restore from a specific backup directory"""
    if not os.path.exists(backup_dir):
        print(f"Backup directory {backup_dir} not found!")
        return
    
    # Remove current files (except backups and venv)
    for item in os.listdir('.'):
        if item not in ['backups', 'venv', '__pycache__']:
            if os.path.isfile(item):
                os.remove(item)
            elif os.path.isdir(item):
                shutil.rmtree(item)
    
    # Copy files from backup
    for item in os.listdir(backup_dir):
        source = os.path.join(backup_dir, item)
        if os.path.isfile(source):
            shutil.copy2(source, '.')
        elif os.path.isdir(source):
            shutil.copytree(source, item)
    
    print(f"Restored from: {backup_dir}")

def list_backups():
    """List all available backups"""
    if not os.path.exists('backups'):
        print("No backups found")
        return
    
    backups = sorted(os.listdir('backups'), reverse=True)
    print("\nAvailable Backups:")
    print("-" * 50)
    for backup in backups:
        print(backup)
    print("-" * 50)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup.py create   - Create a new backup")
        print("  python backup.py restore backup_20240108_164940  - Restore from backup")
        print("  python backup.py list     - List all backups")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        create_backup()
    elif command == "list":
        list_backups()
    elif command == "restore" and len(sys.argv) > 2:
        restore_dir = os.path.join('backups', sys.argv[2])
        restore_backup(restore_dir)
    else:
        print("Invalid command") 