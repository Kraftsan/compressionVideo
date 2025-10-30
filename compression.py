import requests
import os
import tempfile
import time
import logging
from typing import Tuple
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CloudConvertCompressor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.cloudconvert.com/v2"
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        # Настройки качества для CloudConvert
        self.quality_profiles = {
            "low": {
                "video_codec": "h264",
                "crf": 28,
                "preset": "fast",
                "width": 640,
                "audio_bitrate": "64k"
            },
            "medium": {
                "video_codec": "h264",
                "crf": 23,
                "preset": "medium",
                "width": 1280,
                "audio_bitrate": "128k"
            },
            "high": {
                "video_codec": "h264",
                "crf": 20,
                "preset": "slow",
                "width": 1920,
                "audio_bitrate": "192k"
            },
            "social_media": {
                "video_codec": "h264",
                "crf": 23,
                "preset": "medium",
                "width": 1080,
                "height": 1920,
                "fit": "cover",
                "audio_bitrate": "128k"
            }
        }

    def compress_video(self, input_path: str, output_path: str, quality: str = "medium") -> Tuple[bool, str]:
        """
        Сжимает видео через CloudConvert API
        """
        try:
            logger.info(f"Начало сжатия: {input_path} -> {output_path}, качество: {quality}")

            if not self.api_key or self.api_key.startswith("your_cloudconvert_api_key"):
                return False, "CloudConvert API ключ не настроен"

            # Получаем информацию о файле
            file_size = os.path.getsize(input_path)
            logger.info(f"Размер файла: {file_size} bytes")

            if file_size > 100 * 1024 * 1024:  # 100MB лимит CloudConvert
                return False, "Файл слишком большой для CloudConvert (макс. 100MB)"

            # Создаем задание на загрузку
            logger.info("Создаем задание на загрузку...")
            upload_task = self._create_upload_task()
            if not upload_task[0]:
                return False, f"Ошибка создания задачи загрузки: {upload_task[1]}"

            upload_url = upload_task[1]
            upload_form = upload_task[2]
            task_id = upload_task[3]
            logger.info(f"Задание на загрузку создано: {task_id}")

            # Загружаем файл
            logger.info("Загружаем файл на CloudConvert...")
            upload_success = self._upload_file(input_path, upload_url, upload_form)
            if not upload_success:
                return False, "Ошибка загрузки файла на CloudConvert"
            logger.info("Файл успешно загружен")

            # Создаем задание на конвертацию
            logger.info("Создаем задание на конвертацию...")
            convert_task = self._create_convert_task(task_id, quality)
            if not convert_task[0]:
                return False, f"Ошибка создания задачи конвертации: {convert_task[1]}"

            job_id = convert_task[1]
            logger.info(f"Задание на конвертацию создано: {job_id}")

            # Ждем завершения конвертации
            logger.info("Ожидаем завершения конвертации...")
            download_url = self._wait_for_conversion(job_id)
            if not download_url:
                return False, "Ошибка конвертации или таймаут"
            logger.info("Конвертация завершена")

            # Скачиваем результат
            logger.info("Скачиваем результат...")
            download_success = self._download_result(download_url, output_path)
            if not download_success:
                return False, "Ошибка скачивания результата"
            logger.info("Результат скачан")

            return True, "CloudConvert: сжатие завершено успешно!"

        except Exception as e:
            logger.error(f"CloudConvert error: {e}")
            return False, f"Ошибка CloudConvert: {str(e)}"

    def _create_upload_task(self) -> Tuple[bool, str, dict, str]:
        """Создает задание для загрузки файла"""
        try:
            response = requests.post(
                f"{self.base_url}/import/upload",
                headers=self.headers
            )

            if response.status_code == 201:
                data = response.json()
                upload_url = data['data']['url']
                upload_form = data['data']['parameters']
                task_id = data['data']['id']
                return True, upload_url, upload_form, task_id
            else:
                return False, f"HTTP {response.status_code}", {}, ""

        except Exception as e:
            return False, str(e), {}, ""

    def _upload_file(self, file_path: str, upload_url: dict, upload_form: dict) -> bool:
        """Загружает файл на CloudConvert"""
        try:
            with open(file_path, 'rb') as f:
                files = {}
                for key, value in upload_form.items():
                    if key == 'file':
                        files[key] = (os.path.basename(file_path), f, 'video/mp4')
                    else:
                        files[key] = (None, str(value))

                response = requests.post(upload_url, files=files)
                return response.status_code == 201

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False

    def _create_convert_task(self, upload_task_id: str, quality: str) -> Tuple[bool, str]:
        """Создает задание на конвертацию"""
        try:
            if quality not in self.quality_profiles:
                quality = "medium"

            settings = self.quality_profiles[quality]

            job_payload = {
                "tasks": {
                    "convert": {
                        "operation": "convert",
                        "input": upload_task_id,
                        "output_format": "mp4",
                        "video_codec": settings["video_codec"],
                        "crf": settings["crf"],
                        "preset": settings["preset"],
                        "audio_codec": "aac",
                        "audio_bitrate": settings["audio_bitrate"],
                        "fit": settings.get("fit", "scale")
                    },
                    "export": {
                        "operation": "export/url",
                        "input": "convert",
                        "archive_multiple_files": False
                    }
                },
                "tag": "telegram_bot_compression"
            }

            # Добавляем размер если указан
            if "width" in settings:
                job_payload["tasks"]["convert"]["width"] = settings["width"]
            if "height" in settings:
                job_payload["tasks"]["convert"]["height"] = settings["height"]

            response = requests.post(
                f"{self.base_url}/jobs",
                json=job_payload,
                headers=self.headers
            )

            if response.status_code == 201:
                job_id = response.json()['data']['id']
                return True, job_id
            else:
                return False, f"HTTP {response.status_code}"

        except Exception as e:
            return False, str(e)

    def _wait_for_conversion(self, job_id: str, max_wait: int = 300) -> str:
        """Ожидает завершения конвертации"""
        try:
            for i in range(max_wait // 5):  # Проверяем каждые 5 секунд
                time.sleep(5)

                response = requests.get(
                    f"{self.base_url}/jobs/{job_id}",
                    headers=self.headers
                )

                if response.status_code != 200:
                    return ""

                job_data = response.json()
                status = job_data['data']['status']

                if status == 'finished':
                    # Ищем URL для скачивания
                    for task in job_data['data']['tasks']:
                        if task.get('operation') == 'export/url' and task.get('status') == 'finished':
                            return task['result']['files'][0]['url']
                    return ""
                elif status == 'error':
                    logger.error(f"Job error: {job_data}")
                    return ""

            return ""  # Таймаут

        except Exception as e:
            logger.error(f"Wait error: {e}")
            return ""

    def _download_result(self, download_url: str, output_path: str) -> bool:
        """Скачивает результат конвертации"""
        try:
            response = requests.get(download_url, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            return False
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False

    def upload_to_fileio(self, file_path: str) -> Tuple[bool, str]:
        """Загружает файл на file.io и возвращает ссылку для скачивания"""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post('https://file.io', files=files)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    download_url = data['link']
                    return True, download_url
                else:
                    return False, f"File.io error: {data.get('message', 'Unknown error')}"
            else:
                return False, f"HTTP error: {response.status_code}"

        except Exception as e:
            logger.error(f"File.io upload error: {e}")
            return False, f"Upload error: {str(e)}"

    def get_available_qualities(self):
        return list(self.quality_profiles.keys())