import subprocess
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('Setup')

def run_command(command, description):
    """Run a command and log its output."""
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True
        )
        if result.stdout:
            logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {description}:")
        if e.stdout:
            logger.error(e.stdout)
        if e.stderr:
            logger.error(e.stderr)
        return False

def main():
    # Create virtual environment if it doesn't exist
    if not os.path.exists('venv'):
        logger.info("Creating virtual environment...")
        if not run_command([sys.executable, '-m', 'venv', 'venv'], "Create virtual environment"):
            return False
    
    # Determine the pip path
    if sys.platform == 'win32':
        pip_path = os.path.join('venv', 'Scripts', 'pip')
    else:
        pip_path = os.path.join('venv', 'bin', 'pip')
    
    # Upgrade pip
    if not run_command([pip_path, 'install', '--upgrade', 'pip'], "Upgrade pip"):
        return False
    
    # Install dependencies
    if not run_command([pip_path, 'install', '-r', 'requirements.txt'], "Install dependencies"):
        return False
    
    logger.info("Setup completed successfully!")
    logger.info("\nTo activate the virtual environment:")
    if sys.platform == 'win32':
        logger.info("    venv\\Scripts\\activate")
    else:
        logger.info("    source venv/bin/activate")
    logger.info("\nThen run the system with:")
    logger.info("    python run.py")

if __name__ == "__main__":
    main() 