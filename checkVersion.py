import sys
print(f"Python version: {sys.version}")
print(f"Version info: {sys.version_info}")

# Проверяем совместимость
if sys.version_info >= (3, 13):
    print("❌ Python 3.13 может иметь проблемы совместимости с aiogram")
    print("💡 Рекомендуется использовать Python 3.11 или 3.12")
else:
    print("✅ Версия Python подходящая")