import patch_pil  # noqa: F401

import os
import logging
import tempfile
import asyncio
from typing import Dict, Any

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

from config import BOT_TOKEN, MAX_DOWNLOAD_SIZE, MAX_UPLOAD_SIZE
from compression import MoviePyCompressor
from video_utils import format_file_size, get_video_info

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем роутер
router = Router()

# Инициализация компрессора
compressor = MoviePyCompressor()

# Хранилище временных файлов пользователей
user_temp_files: Dict[int, Dict[str, Any]] = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для сжатия видео для социальных сетей. 

📹 Просто отправь мне видео файл, и я предложу варианты сжатия.

✅ Поддерживаемые форматы: MP4, MOV, AVI, MKV
✅ Максимальный размер: 20MB

Для начала отправь мне видео! 🎬
    """
    await message.answer(welcome_text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
🤖 <b>Помощь по использованию бота:</b>

📹 <b>Как использовать:</b>
1. Отправьте видео файл (до 20MB)
2. Я покажу информацию о файле и варианты сжатия
3. Выберите качество сжатия
4. Получите сжатое видео!

🎯 <b>Качества сжатия:</b>
• 🔴 Низкое - максимальное сжатие (480p)
• 🟡 Среднее - баланс качества/размера (720p)  
• 🟢 Высокое - лучшее качество (1080p)
• 📱 Соцсети - для Instagram/TikTok (1080x1920)

Попробуйте отправить видео прямо сейчас! 🎥
    """
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(F.video)
async def handle_video(message: Message):
    """Обработчик получения видео"""
    await process_video_message(message, message.video)


@router.message(F.document & (F.document.mime_type.startswith('video/') | (F.document.mime_type == 'video/quicktime')))
async def handle_video_document(message: Message):
    """Обработчик получения видео как документа (включая MOV)"""
    await process_video_message(message, message.document)


async def process_video_message(message: Message, video_obj):
    """Общая логика обработки видео - ТЕПЕРЬ ТОЛЬКО СКАЧИВАНИЕ И ПОКАЗ ИНФОРМАЦИИ"""
    try:
        user_id = message.from_user.id

        # ПРОВЕРКА РАЗМЕРА ДЛЯ СКАЧИВАНИЯ
        max_download_size = 20 * 1024 * 1024
        if video_obj.file_size > max_download_size:
            await message.answer(
                f"❌ Файл слишком большой для обработки! 📦\n"
                f"Максимальный размер: {format_file_size(max_download_size)}\n\n"
                f"Пожалуйста, отправьте файл меньшего размера."
            )
            return

        # Сообщение о начале скачивания
        processing_msg = await message.answer("⏳ Скачиваю видео... Пожалуйста, подождите.")

        # Скачивание видео
        file_id = video_obj.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_input:
            input_path = temp_input.name

        try:
            # Скачиваем файл
            await message.bot.download_file(file_path, input_path)

        except Exception as download_error:
            await processing_msg.edit_text(f"❌ Ошибка при скачивании файла: {download_error}")
            try:
                os.unlink(input_path)
            except:
                pass
            return

        original_size = os.path.getsize(input_path)

        # Получаем информацию о видео
        video_info = get_video_info(input_path)

        if not video_info:
            await processing_msg.edit_text("❌ Не удалось получить информацию о видео файле")
            try:
                os.unlink(input_path)
            except:
                pass
            return

        # Сохраняем временный файл для пользователя
        if user_id not in user_temp_files:
            user_temp_files[user_id] = {}

        user_temp_files[user_id]['input_path'] = input_path
        user_temp_files[user_id]['original_size'] = original_size
        user_temp_files[user_id]['video_info'] = video_info

        await processing_msg.delete()

        # Показываем информацию о файле и кнопки выбора качества
        duration_min = int(video_info['duration'] // 60)
        duration_sec = int(video_info['duration'] % 60)

        info_text = (
            f"📊 <b>Информация о видео:</b>\n"
            f"• 📦 Размер: {format_file_size(original_size)}\n"
            f"• ⏱ Длительность: {duration_min}:{duration_sec:02d}\n"
            f"• 🖼 Разрешение: {video_info['width']}x{video_info['height']}\n"
            f"• 🔤 Кодек: {video_info['codec'].upper()}\n\n"
            f"🎯 <b>Выберите качество сжатия:</b>"
        )

        builder = InlineKeyboardBuilder()

        qualities = [
            ("🔴 Низкое (480p)", "compress_low"),
            ("🟡 Среднее (720p)", "compress_medium"),
            ("🟢 Высокое (1080p)", "compress_high"),
            ("📱 Соцсети (Reels)", "compress_social")
        ]

        for text, callback_data in qualities:
            builder.button(text=text, callback_data=callback_data)

        builder.adjust(2)  # 2 кнопки в ряду

        await message.answer(
            info_text,
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        logger.error(f"Error processing video message: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке видео: {str(e)}")


@router.callback_query(F.data.startswith("compress_"))
async def process_compression_selection(callback: CallbackQuery):
    """Обработчик выбора сжатия"""
    try:
        user_id = callback.from_user.id
        quality = callback.data.replace('compress_', '')

        # Проверяем есть ли сохраненный файл
        if user_id not in user_temp_files or 'input_path' not in user_temp_files[user_id]:
            await callback.message.edit_text("❌ Файл не найден. Пожалуйста, отправьте видео заново.")
            await callback.answer()
            return

        input_path = user_temp_files[user_id]['input_path']
        original_size = user_temp_files[user_id]['original_size']
        video_info = user_temp_files[user_id]['video_info']

        quality_names = {
            'low': '🔴 Низкое',
            'medium': '🟡 Среднее',
            'high': '🟢 Высокое',
            'social': '📱 Соцсети'
        }

        await callback.message.edit_text(f"⏳ Начинаю сжатие в качестве: {quality_names[quality]}...")

        # Сжатие видео
        output_path = input_path.replace('.mp4', '_compressed.mp4')

        # Запускаем сжатие в отдельном потоке
        loop = asyncio.get_event_loop()
        success, result_message = await loop.run_in_executor(
            None,
            compressor.compress_video,
            input_path, output_path, quality
        )

        if success and os.path.exists(output_path):
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100

            # Проверка размера результата
            if compressed_size <= MAX_UPLOAD_SIZE:
                # Файл подходит для отправки через Telegram
                compressed_video = FSInputFile(output_path)
                await callback.message.answer_video(
                    video=compressed_video,
                    caption=(
                        f"✅ Видео успешно сжато! 🎉\n"
                        f"📊 Исходный размер: {format_file_size(original_size)}\n"
                        f"📊 Сжатый размер: {format_file_size(compressed_size)}\n"
                        f"📈 Сжатие: {compression_ratio:.1f}%\n"
                        f"🎯 Качество: {quality_names[quality]}"
                    )
                )
            else:
                await callback.message.answer(
                    f"✅ Видео сжато, но файл слишком большой для Telegram 📦\n\n"
                    f"📊 Исходный размер: {format_file_size(original_size)}\n"
                    f"📊 Сжатый размер: {format_file_size(compressed_size)}\n"
                    f"📈 Сжатие: {compression_ratio:.1f}%\n"
                    f"🎯 Качество: {quality_names[quality]}\n\n"
                    f"❌ К сожалению, сжатый файл все еще превышает лимит Telegram.\n"
                    f"Попробуйте выбрать более низкое качество сжатия."
                )

            # Удаляем сообщение с кнопками
            await callback.message.delete()

        else:
            await callback.message.edit_text(f"❌ Ошибка при сжатии: {result_message}")

        await callback.answer()

    except Exception as e:
        logger.error(f"Error in compression selection: {e}")
        await callback.message.edit_text(f"❌ Произошла ошибка при сжатии: {str(e)}")
        await callback.answer()

    finally:
        # Очистка временных файлов
        await cleanup_user_files(user_id)


async def cleanup_user_files(user_id: int):
    """Очистка временных файлов пользователя"""
    await asyncio.sleep(1)  # Задержка для освобождения файлов

    if user_id in user_temp_files:
        try:
            files_to_delete = []
            if 'input_path' in user_temp_files[user_id]:
                files_to_delete.append(user_temp_files[user_id]['input_path'])
            if 'output_path' in user_temp_files[user_id]:
                files_to_delete.append(user_temp_files[user_id]['output_path'])

            for file_path in files_to_delete:
                if file_path and os.path.exists(file_path):
                    for attempt in range(3):
                        try:
                            os.unlink(file_path)
                            break
                        except (PermissionError, OSError):
                            await asyncio.sleep(0.5)

            # Удаляем запись пользователя
            del user_temp_files[user_id]

        except Exception as e:
            logger.error(f"Error cleaning user files: {e}")


@router.message()
async def handle_other_messages(message: Message):
    """Обработчик всех остальных сообщений"""
    await message.answer(
        "🤖 Отправьте мне видео файл для сжатия или используйте команды:\n"
        "/start - Начать работу\n"
        "/help - Помощь"
    )


async def main():
    """Основная функция запуска бота"""
    try:
        bot = Bot(token=BOT_TOKEN)

        # Проверка подключения
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username} - {bot_info.first_name}")

        dp = Dispatcher()
        dp.include_router(router)

        logger.info("Бот запускается...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")


if __name__ == '__main__':
    asyncio.run(main())