from BCN.Proccesing.utils import Utils as IOP
import telebot
from BCN.Communication.EmailCom import EmailCommunicator as TWM
from BCN.Proccesing.Identifier import Identifier as ID
from telebot import util, types
import threading
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

io = IOP()
config = io.load_json("data/env.json")
twm = TWM()
idt = ID()
MAIN_USER_ID = config["MAIN_USER_ID"]
bot = telebot.TeleBot(config["BOT_TOKEN"])

# Создаем словарь с доступными командами и их описанием
BOT_COMMANDS = {
    "/start": "Начать работу с ботом",
    "/help": "Показать список доступных команд",
    "/list": "Показать список доступных устройств",
    "/send": "Отправить команду на устройство (формат: /send [device_name] [command])",
    "/dialog": "Начать диалог с устройством (формат: /dialog [device_name])",
    "/exit": "Выйти из режима диалога с устройством"
}

# Словарь для хранения активных диалогов с устройствами (user_id: device_name)
active_dialogs = {}

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == MAIN_USER_ID:
        bot.send_message(
            message.chat.id, 
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"Я бот для удаленного управления устройствами. "
            f"Используй /help для просмотра доступных команд."
        )
    else:
        bot.send_message(
            message.chat.id, 
            "⚠️ У вас нет прав для использования этого бота.\n"
            "Обратитесь к администратору для получения доступа."
        )

@bot.message_handler(commands=['help'])
def help_command(message):
    if message.from_user.id != MAIN_USER_ID:
        bot.send_message(message.chat.id, "⚠️ У вас нет прав для использования этого бота.")
        return
        
    help_text = "📌 *Доступные команды:*\n\n"
    for cmd, desc in BOT_COMMANDS.items():
        help_text += f"• `{cmd}` - {desc}\n"
    
    help_text += "\n💡 Пример использования команды send:\n`/send my_pc reboot`"
    
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['list'])
def list_devices(message):
    if message.from_user.id != MAIN_USER_ID:
        bot.send_message(message.chat.id, "⚠️ У вас нет прав для использования этого бота.")
        return
        
    # Загружаем актуальные данные
    idt.twmcd = io.load_json("./data/twmcd.json")
    
    if not idt.twmcd:
        bot.send_message(message.chat.id, "❌ Устройства не найдены. Файл twmcd.json пуст или не существует.")
        return
        
    devices_text = "📱 *Доступные устройства:*\n\n"
    for address, data in idt.twmcd.items():
        device_name = data.get('name', 'Неизвестное устройство')
        status = data.get('status', 'Статус неизвестен')
        devices_text += f"• *{device_name}*\n  └ Адрес: `{address}`\n"
    
    devices_text += "\nДля отправки команды используйте:\n`/send [device_name] [command]`"
    
    bot.send_message(message.chat.id, devices_text, parse_mode="Markdown")

@bot.message_handler(commands=["send"])
def sendCommand(message: types.Message):
    if message.from_user.id == MAIN_USER_ID:
        rawCommand = util.extract_arguments(message.text)
        if not rawCommand or " " not in rawCommand:
            bot.send_message(
                message.chat.id, 
                "⚠️ *Неверный формат команды*\n\n"
                "Правильный формат: `/send [device_name] [command]`\n\n"
                "Пример: `/send my_pc reboot`\n\n"
                "Используйте `/list` для просмотра доступных устройств.",
                parse_mode="Markdown"
            )
            return
            
        computerName = rawCommand.split(" ")[0]
        command = rawCommand.split(" ", 1)[1]
        
        # Перезагружаем файл twmcd.json перед каждой проверкой
        idt.twmcd = io.load_json("./data/twmcd.json")
        
        for address, data in idt.twmcd.items():
            if data.get("name") == computerName:
                twm.send(command, address, "IC", f"Listen {data['name']}! I want you to do {command}")
                bot.send_message(
                    message.chat.id, 
                    f"✅ Команда успешно отправлена!\n\n"
                    f"• Устройство: *{data['name']}*\n"
                    f"• Адрес: `{address}`\n"
                    f"• Команда: `{command}`",
                    parse_mode="Markdown"
                )
                return
                
        # Получаем список доступных устройств для сообщения об ошибке
        available_devices = [data.get('name', 'unknown') for data in idt.twmcd.values() if data.get('name')]
        devices_list = ", ".join([f"`{name}`" for name in available_devices]) if available_devices else "нет доступных устройств"
        
        bot.send_message(
            message.chat.id, 
            f"❌ *Ошибка:* Устройство `{computerName}` не найдено!\n\n"
            f"*Доступные устройства:*\n{devices_list}\n\n"
            f"Используйте `/list` для получения подробной информации.",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id, 
            "⚠️ У вас нет прав для использования этого бота.\n"
            "Обратитесь к администратору для получения доступа."
        )

@bot.message_handler(commands=["dialog"])
def start_dialog(message: types.Message):
    if message.from_user.id != MAIN_USER_ID:
        bot.send_message(message.chat.id, "⚠️ У вас нет прав для использования этого бота.")
        return
        
    device_name = util.extract_arguments(message.text)
    if not device_name:
        bot.send_message(
            message.chat.id, 
            "⚠️ *Неверный формат команды*\n\n"
            "Правильный формат: `/dialog [device_name]`\n\n"
            "Пример: `/dialog my_pc`\n\n"
            "Используйте `/list` для просмотра доступных устройств.",
            parse_mode="Markdown"
        )
        return
    
    # Перезагружаем файл twmcd.json перед проверкой
    idt.twmcd = io.load_json("./data/twmcd.json")
    
    # Проверяем существование устройства
    device_exists = False
    device_address = None
    for address, data in idt.twmcd.items():
        if data.get("name") == device_name:
            device_exists = True
            device_address = address
            break
    
    if not device_exists:
        # Получаем список доступных устройств для сообщения об ошибке
        available_devices = [data.get('name', 'unknown') for data in idt.twmcd.values() if data.get('name')]
        devices_list = ", ".join([f"`{name}`" for name in available_devices]) if available_devices else "нет доступных устройств"
        
        bot.send_message(
            message.chat.id, 
            f"❌ *Ошибка:* Устройство `{device_name}` не найдено!\n\n"
            f"*Доступные устройства:*\n{devices_list}\n\n"
            f"Используйте `/list` для получения подробной информации.",
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем информацию о начатом диалоге
    active_dialogs[message.from_user.id] = {
        "name": device_name,
        "address": device_address
    }
    
    bot.send_message(
        message.chat.id, 
        f"✅ *Диалог с устройством начат!*\n\n"
        f"• Устройство: *{device_name}*\n"
        f"• Адрес: `{device_address}`\n\n"
        f"Теперь все сообщения будут отправляться на это устройство.\n"
        f"Для выхода из режима диалога используйте команду `/exit`.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["exit"])
def exit_dialog(message: types.Message):
    if message.from_user.id != MAIN_USER_ID:
        bot.send_message(message.chat.id, "⚠️ У вас нет прав для использования этого бота.")
        return
    
    if message.from_user.id in active_dialogs:
        device_name = active_dialogs[message.from_user.id]["name"]
        del active_dialogs[message.from_user.id]
        bot.send_message(
            message.chat.id, 
            f"✅ Диалог с устройством *{device_name}* завершен.\n\n"
            f"Вы вернулись в обычный режим.",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            message.chat.id, 
            "ℹ️ Вы не находитесь в режиме диалога с устройством.",
            parse_mode="Markdown"
        )

@bot.message_handler(content_types=['text'])
def handle_message(message: types.Message):
    if message.from_user.id != MAIN_USER_ID:
        return
    
    # Проверяем, не является ли сообщение командой
    if message.text.startswith('/'):
        # Это команда, которую мы не обработали ранее - показываем справку
        if not any(message.text.startswith(cmd) for cmd in BOT_COMMANDS.keys()):
            bot.send_message(
                message.chat.id, 
                "❓ Не понимаю вашу команду. Используйте следующие команды:\n\n"
                "• `/help` - список всех команд\n"
                "• `/list` - список всех устройств\n"
                "• `/send [device_name] [command]` - отправка команды\n"
                "• `/dialog [device_name]` - начать диалог с устройством\n"
                "• `/exit` - выйти из режима диалога",
                parse_mode="Markdown"
            )
        return
    
    # Проверяем, находится ли пользователь в режиме диалога
    if message.from_user.id in active_dialogs:
        device_info = active_dialogs[message.from_user.id]
        device_name = device_info["name"]
        device_address = device_info["address"]
        command = message.text
        
        # Отправляем команду устройству
        twm.send(command, device_address, "IC", f"Listen {device_name}! I want you to do {command}")
        
        bot.send_message(
            message.chat.id, 
            f"✅ Команда отправлена на устройство *{device_name}*:\n`{command}`",
            parse_mode="Markdown"
        )
    else:
        # Пользователь не в режиме диалога, показываем подсказку
        bot.send_message(
            message.chat.id, 
            "ℹ️ Вы не в режиме диалога с устройством.\n\n"
            "Используйте:\n"
            "• `/dialog [device_name]` - для начала диалога с устройством\n"
            "• `/send [device_name] [command]` - для отправки команды\n"
            "• `/help` - список всех команд",
            parse_mode="Markdown"
        )

# Функция для запуска бота в отдельном потоке
def start_bot():
    logging.info("Starting Telegram Bot in a separate thread")
    bot.polling(none_stop=True, interval=0)

# Запуск бота в отдельном потоке
telegram_thread = None

def start_bot_thread():
    global telegram_thread
    if telegram_thread is None or not telegram_thread.is_alive():
        telegram_thread = threading.Thread(target=start_bot)
        telegram_thread.daemon = True  # Поток завершится, когда завершится основной поток
        telegram_thread.start()
        logging.info("Telegram bot thread started")

def stop_bot():
    global telegram_thread
    if telegram_thread and telegram_thread.is_alive():
        bot.stop_polling()
        telegram_thread.join(timeout=3)
        logging.info("Telegram bot stopped")

# Не запускаем бота автоматически при импорте модуля
# Вместо этого, бот будет запущен из initiate_server
