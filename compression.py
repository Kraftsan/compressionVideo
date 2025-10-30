import os
import logging
from typing import Tuple
from moviepy.editor import VideoFileClip

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MoviePyCompressor:
    def __init__(self):
        self.quality_profiles = {
            "low": {
                "height": 480,
                "bitrate": "800k",
                "audio_bitrate": "64k",
            },
            "medium": {
                "height": 720,
                "bitrate": "1500k",
                "audio_bitrate": "128k",
            },
            "high": {
                "height": 1080,
                "bitrate": "3000k",
                "audio_bitrate": "192k",
            },
            "social_media": {
                "height": 1920,
                "width": 1080,
                "bitrate": "2500k",
                "audio_bitrate": "128k",
            }
        }

    def compress_video(self, input_path: str, output_path: str, quality: str = "medium") -> Tuple[bool, str]:
        """Сжимает видео используя MoviePy"""
        try:
            if quality not in self.quality_profiles:
                quality = "medium"

            settings = self.quality_profiles[quality]

            logger.info(f"Начало сжатия MoviePy: {input_path} -> {output_path}")
            logger.info(f"Настройки: {settings}")

            # Загружаем видео
            clip = VideoFileClip(input_path)

            # Ресайзим видео
            if quality == "social_media":
                # Для сторис/рилсов - вертикальный формат
                clip_resized = clip.resize(height=settings["height"])
                if clip_resized.w > settings["width"]:
                    # Обрезаем по ширине для вертикального формата
                    x_center = clip_resized.w / 2
                    clip_resized = clip_resized.crop(
                        x1=x_center - settings["width"] / 2,
                        width=settings["width"]
                    )
            else:
                # Обычное сжатие с изменением высоты
                clip_resized = clip.resize(height=settings["height"])

            # Сохраняем с настройками качества
            clip_resized.write_videofile(
                output_path,
                bitrate=settings["bitrate"],
                audio_bitrate=settings["audio_bitrate"],
                verbose=False,
                logger=None
            )

            # Закрываем клипы для освобождения памяти
            clip.close()
            clip_resized.close()

            # Проверяем что файл создан
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                logger.info(f"Сжатие завершено. Размер: {output_size} байт")
                return True, "MoviePy: сжатие завершено успешно!"
            else:
                return False, "Выходной файл не создан"

        except Exception as e:
            logger.error(f"MoviePy compression error: {e}")
            return False, f"Ошибка MoviePy: {str(e)}"

    def get_available_qualities(self):
        return list(self.quality_profiles.keys())