import os
import math
import subprocess
import json


def get_video_info(file_path: str) -> dict:
    """Получает информацию о видео файле используя ffprobe"""
    try:
        # Команда для получения информации о видео в JSON формате
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return get_video_info_fallback(file_path)

        probe_data = json.loads(result.stdout)

        video_stream = next((stream for stream in probe_data['streams'] if stream['codec_type'] == 'video'), None)
        audio_stream = next((stream for stream in probe_data['streams'] if stream['codec_type'] == 'audio'), None)

        if not video_stream:
            return get_video_info_fallback(file_path)

        file_size = os.path.getsize(file_path)
        duration = float(video_stream.get('duration', probe_data['format'].get('duration', 0)))

        return {
            'duration': duration,
            'width': int(video_stream.get('width', 0)),
            'height': int(video_stream.get('height', 0)),
            'codec': video_stream.get('codec_name', 'unknown'),
            'bit_rate': int(video_stream.get('bit_rate', probe_data['format'].get('bit_rate', 0))),
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'has_audio': audio_stream is not None
        }

    except Exception as e:
        print(f"Error getting video info with ffprobe: {e}")
        return get_video_info_fallback(file_path)


def get_video_info_fallback(file_path: str) -> dict:
    """Резервный метод получения информации о видео"""
    try:
        file_size = os.path.getsize(file_path)

        # Пытаемся получить длительность через MoviePy как запасной вариант
        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(file_path) as clip:
                duration = clip.duration
                width, height = clip.size

            return {
                'duration': duration,
                'width': width,
                'height': height,
                'codec': 'unknown',
                'bit_rate': 0,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'has_audio': True  # предполагаем что есть аудио
            }
        except:
            # Если MoviePy тоже не работает, возвращаем базовую информацию
            return {
                'duration': 0,
                'width': 0,
                'height': 0,
                'codec': 'unknown',
                'bit_rate': 0,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'has_audio': True
            }

    except Exception as e:
        print(f"Error in fallback video info: {e}")
        return None


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в читаемый вид"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """Форматирует длительность в читаемый вид"""
    if seconds == 0:
        return "0:00"

    minutes = int(seconds // 60)
    secs = int(seconds % 60)

    if minutes > 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"