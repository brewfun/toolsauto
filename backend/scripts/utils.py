import subprocess
import logging
import os

# Lấy đường dẫn đến thư mục gốc của dự án
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# Tạo thư mục logs nếu chưa tồn tại
os.makedirs(LOG_DIR, exist_ok=True)

# Thiết lập logging để lưu log vào file trong thư mục gốc/logs/ và in ra console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'app.log')),  # Lưu vào k8s-auto-installer/logs/app.log
        logging.StreamHandler()  # In log ra console
    ]
)
logger = logging.getLogger(__name__)

def run_command(command, shell=True):
    """
    Chạy một shell command và trả về output.
    
    Args:
        command (str): Lệnh shell để chạy (e.g., 'apt update').
        shell (bool): Sử dụng shell=True để chạy command như trong terminal.
    
    Returns:
        tuple: (success: bool, output: str)
        - success: True nếu chạy thành công, False nếu có lỗi.
        - output: Kết quả hoặc lỗi từ command.
    """
    try:
        # Chạy command và lấy output
        result = subprocess.run(
            command,
            shell=shell,
            check=True,  # Raise exception nếu command fail
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Trả về output dạng string
        )
        logger.info(f"Command '{command}' executed successfully")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        # Log lỗi nếu command fail
        logger.error(f"Command '{command}' failed: {e.stderr}")
        return False, e.stderr
    except Exception as e:
        # Log các lỗi khác (e.g., permission issues)
        logger.error(f"Unexpected error: {str(e)}")
        return False, str(e)

if __name__ == "__main__":
    # Test hàm run_command
    success, output = run_command("echo Hello, Python!")
    if success:
        print(f"Output: {output}")
    else:
        print(f"Error: {output}")