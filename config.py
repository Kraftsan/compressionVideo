import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = "API_TOKEN"

# Настройки бота
MAX_DOWNLOAD_SIZE = 20 * 1024 * 1024  # 20MB (реальное ограничение Telegram на скачивание)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024   # 50MB (ограничение Telegram на отправку)
COMPRESSED_QUALITY = "medium"  # low, medium, high

# Настройки CloudConvert
CLOUDCONVERT_BASE_URL = "https://api.cloudconvert.com/v2"