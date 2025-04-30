from BCN.Proccesing.utils import Utils as IOP
import telebot
from BCN.twm import TellWithMe as TWM
from telebot import util, types

io = IOP()
config = io.load_json("env.json")
twm = TWM()
MAIN_USER_ID = config["MAIN_USER_ID"]
bot = telebot.TeleBot(config["BOT_TOKEN"])

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == MAIN_USER_ID:
        bot.send_message(message.chat.id, 'Start command do nothing, just say hello')
    else:
        bot.send_message(message.chat.id, 'You are not authorized to use this bot.')

@bot.message_handler(commands=["send"])
def sendCommand(message: types.Message):
    if message.from_user.id == MAIN_USER_ID:
        rawCommand = util.extract_arguments(message.text)
        computerName = rawCommand.split("/")[0]
        command = rawCommand.split("")[1]
        for address, data in twm.twmcd.items():
            if data["name"] == computerName:
                twm.send(twm.compile_command("IC", {"command": command}), address, "IC", f"Listen {data['name']}! I want to you do {command}")
                bot.send_message(message.chat.id, f"Command {command} sent to {data['name']}")
    else:
        bot.send_message(message.chat.id, 'You are not authorized to use this bot.')