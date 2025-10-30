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

from config import BOT_TOKEN, MAX_DOWNLOAD_SIZE, MAX_UPLOAD_SIZE, CLOUDCONVERT_API_KEY
from compression import MoviePyCompressor
from video_utils import format_file_size

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем роутер
router = Router()

# Инициализация компрессора
compressor = MoviePyCompressor()

# Хранилище состояний пользователей
user_states: Dict[int, Dict[str, Any]] = {}


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user = message.from_user
    welcome_text = f"""
👋 Привет, {user.first_name}!

Я бот для сжатия видео для социальных сетей. 

📹 Отправь мне видео файл или используй команду /compress для выбора настроек сжатия.

✅ Поддерживаемые форматы: MP4, MOV, AVI, MKV
✅ Максимальный размер: 100MB

📎 Если сжатый файл будет слишком большим для Telegram, я пришлю вам прямую ссылку для скачивания!

Для начала просто отправь мне видео! 🎬
    """
    await message.answer(welcome_text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = f"""
🤖 <b>Помощь по использованию бота:</b>

📹 <b>Как использовать:</b>
1. Отправьте видео файл (до {format_file_size(MAX_DOWNLOAD_SIZE)})
2. Выберите качество сжатия
3. Получите сжатое видео!

💡 <b>Особенности:</b>
• Если файл слишком большой для Telegram - получите прямую ссылку для скачивания
• Ссылки действительны в течение 14 дней
• Файлы автоматически удаляются после скачивания

⚙️ <b>Команды:</b>
/start - Начать работу
/help - Показать эту справку  
/compress - Выбрать настройки сжатия

🎯 <b>Качества сжатия:</b>
• 🔴 Низкое - максимальное сжатие
• 🟡 Среднее - баланс качества/размера  
• 🟢 Высокое - лучшее качество
• 📱 Соцсети - оптимизировано для Instagram/TikTok

Попробуйте отправить видео прямо сейчас! 🎥
    """
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("compress"))
async def cmd_compress(message: Message):
    """Показывает варианты сжатия"""
    builder = InlineKeyboardBuilder()

    qualities = [
        ("🔴 Низкое", "quality_low"),
        ("🟡 Среднее", "quality_medium"),
        ("🟢 Высокое", "quality_high"),
        ("📱 Соцсети", "quality_social_media")
    ]

    for text, callback_data in qualities:
        builder.button(text=text, callback_data=callback_data)

    builder.adjust(2)  # 2 кнопки в ряду

    await message.answer(
        "🎛️ <b>Выберите качество сжатия:</b>\n\n"
        "• 🔴 Низкое - максимальное сжатие\n"
        "• 🟡 Среднее - баланс качества/размера\n"
        "• 🟢 Высокое - лучшее качество\n"
        "• 📱 Соцсети - для Instagram/TikTok\n\n"
        "💡 <i>Если файл будет слишком большим для Telegram, вы получите прямую ссылку для скачивания</i>",
        reply_markup=builder.as_markup(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data.startswith("quality_"))
async def process_quality_selection(callback: CallbackQuery):
    """Обработчик выбора качества"""
    quality = callback.data.replace('quality_', '')

    quality_names = {
        'low': '🔴 Низкое',
        'medium': '🟡 Среднее',
        'high': '🟢 Высокое',
        'social_media': '📱 Соцсети'
    }

    # Сохраняем выбор пользователя
    user_id = callback.from_user.id
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['selected_quality'] = quality

    await callback.message.edit_text(
        f"✅ Выбрано качество: {quality_names[quality]}\n\n"
        "Теперь отправьте мне видео для сжатия! 🎥\n\n"
        "💡 <i>Если файл будет слишком большим, вы получите прямую ссылку для скачивания</i>"
    )
    await callback.answer()


@router.message(F.video)
async def handle_video(message: Message):
    """Обработчик получения видео"""
    await process_video_message(message, message.video)


@router.message(F.document & (F.document.mime_type.startswith('video/') | (F.document.mime_type == 'video/quicktime')))
async def handle_video_document(message: Message):
    """Обработчик получения видео как документа (включая MOV)"""
    await process_video_message(message, message.document)


async def process_video_message(message: Message, video_obj):
    """Общая логика обработки видео"""
    try:
        user_id = message.from_user.id

        # ПРОВЕРКА РАЗМЕРА ДЛЯ СКАЧИВАНИЯ
        if video_obj.file_size > MAX_DOWNLOAD_SIZE:
            await message.answer(
                f"❌ Файл слишком большой для обработки! 📦\n"
                f"Максимальный размер: {format_file_size(MAX_DOWNLOAD_SIZE)}\n\n"
                f"Telegram не позволяет боту скачивать файлы больше {format_file_size(MAX_DOWNLOAD_SIZE)}.\n"
                f"Пожалуйста, отправьте файл меньшего размера."
            )
            return

        # Сообщение о начале обработки
        processing_msg = await message.answer("⏳ Скачиваю видео... Пожалуйста, подождите.")

        # Скачивание видео
        file_id = video_obj.file_id
        file = await message.bot.get_file(file_id)
        file_path = file.file_path

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_input:
            input_path = temp_input.name

        try:
            # Скачиваем файл с таймаутом
            await asyncio.wait_for(
                message.bot.download_file(file_path, input_path),
                timeout=300  # 5 минут таймаут на скачивание
            )
        except asyncio.TimeoutError:
            await processing_msg.edit_text("❌ Таймаут при скачивании файла")
            try:
                os.unlink(input_path)
            except:
                pass
            return

        original_size = os.path.getsize(input_path)
        logger.info(f"Файл скачан: {format_file_size(original_size)}")

        await processing_msg.edit_text("⏳ Сжимаю видео... Это может занять несколько минут.")

        # Сжатие видео
        output_path = input_path.replace('.mp4', '_compressed.mp4')

        # Получаем выбранное качество или используем среднее по умолчанию
        selected_quality = user_states.get(user_id, {}).get('selected_quality', 'medium')

        # Запускаем сжатие в отдельном потоке чтобы не блокировать бота
        loop = asyncio.get_event_loop()
        success, result_message = await loop.run_in_executor(
            None,
            compressor.compress_video,
            input_path, output_path, selected_quality
        )

        if success and os.path.exists(output_path):
            compressed_size = os.path.getsize(output_path)
            compression_ratio = (1 - compressed_size / original_size) * 100

            # ПРОВЕРКА РАЗМЕРА РЕЗУЛЬТАТА ДЛЯ ОТПРАВКИ
            if compressed_size <= MAX_UPLOAD_SIZE:
                # Файл подходит для отправки через Telegram
                compressed_video = FSInputFile(output_path)
                await message.answer_video(
                    video=compressed_video,
                    caption=(
                        f"✅ Видео успешно сжато! 🎉\n"
                        f"📊 Исходный размер: {format_file_size(original_size)}\n"
                        f"📊 Сжатый размер: {format_file_size(compressed_size)}\n"
                        f"📈 Сжатие: {compression_ratio:.1f}%\n"
                        f"🎯 Качество: {selected_quality}"
                    )
                )
                await processing_msg.delete()
            else:
                # Файл слишком большой - отправляем ссылку
                await processing_msg.edit_text("📤 Файл слишком большой для Telegram. Загружаю на файлообменник...")

                # Загружаем на file.io
                upload_success, download_url = await loop.run_in_executor(
                    None,
                    compressor.upload_to_fileio,
                    output_path
                )

                if upload_success:
                    await message.answer(
                        f"✅ Видео успешно сжато! 🎉\n\n"
                        f"📊 Исходный размер: {format_file_size(original_size)}\n"
                        f"📊 Сжатый размер: {format_file_size(compressed_size)}\n"
                        f"📈 Сжатие: {compression_ratio:.1f}%\n"
                        f"🎯 Качество: {selected_quality}\n\n"
                        f"📎 <b>Скачайте файл по ссылке:</b>\n"
                        f"<code>{download_url}</code>\n\n"
                        f"💡 <i>Ссылка действительна 14 дней. Файл удалится после скачивания.</i>",
                        parse_mode=ParseMode.HTML
                    )
                    await processing_msg.delete()
                else:
                    await processing_msg.edit_text(
                        f"✅ Видео сжато, но файл слишком большой для Telegram ({format_file_size(compressed_size)}).\n"
                        f"❌ Не удалось загрузить на файлообменник: {download_url}"
                    )
        else:
            await processing_msg.edit_text(f"❌ Ошибка при сжатии: {result_message}")

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await message.answer(f"❌ Произошла ошибка при обработке видео: {str(e)}")

    finally:
        # Очистка временных файлов
        try:
            if 'input_path' in locals() and os.path.exists(input_path):
                os.unlink(input_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.unlink(output_path)
        except Exception as e:
            logger.error(f"Error cleaning temp files: {e}")


@router.message()
async def handle_other_messages(message: Message):
    """Обработчик всех остальных сообщений"""
    await message.answer(
        "🤖 Отправьте мне видео файл для сжатия или используйте команды:\n"
        "/start - Начать работу\n"
        "/help - Помощь\n"
        "/compress - Выбрать качество сжатия"
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