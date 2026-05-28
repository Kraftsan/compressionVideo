# quick_test.py
import asyncio
import logging

logging.basicConfig(level=logging.INFO)


async def test():
    from aiogram import Bot
\\revoke key
    bot = Bot(token="8214580449:AAEIJkrtDAws7_FjEDSK5hmFaYoIH5-tw-w")

    try:
        me = await bot.get_me()
        print(f"✅ Бот активен: @{me.username}")
        print("✅ Токен рабочий")
        print("📝 Теперь напишите /start боту в Telegram")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(test())
