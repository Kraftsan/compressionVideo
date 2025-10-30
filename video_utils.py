import os
import math


def get_video_info(file_path: str) -> dict:
    """Получает информацию о видео файле"""
    try:
        import ffmpeg

        probe = ffmpeg.probe(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)

        if not video_stream:
            return None

        file_size = os.path.getsize(file_path)

        return {
            'duration': float(video_stream.get('duration', 0)),
            'width': int(video_stream['width']),
            'height': int(video_stream['height']),
            'codec': video_stream.get('codec_name', 'unknown'),
            'bit_rate': int(video_stream.get('bit_rate', 0)),
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'has_audio': audio_stream is not None
        }
    except Exception as e:
        print(f"Error getting video info: {e}")
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