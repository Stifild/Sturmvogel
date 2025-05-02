import imaplib, email, smtplib
import logging
import base64
from BCN.Proccesing.Decoder import *
from BCN.Proccesing.Identifier import Identifier
from BCN.Proccesing.utils import Utils
from BCN.Proccesing.Coder import compile_command

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class IMAPServerConnection:
    def __init__(self, server_address: str, server_port: int, us_name: str, us_password: str):
        self.server_address = server_address
        self.server_port = server_port
        self.us_name = us_name
        self.us_password = us_password

    def __enter__(self) -> imaplib.IMAP4_SSL:
        self.box = imaplib.IMAP4_SSL(self.server_address, self.server_port)
        self.box.login(self.us_name, self.us_password)
        return self.box

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"IMAP error occurred: {exc_val}") 
        self.box.close()
        self.box.logout()

class SMTPServerConnection:
    def __init__(self, server_address: str, server_port: int, us_name: str, us_password: str):
        self.server_address = server_address
        self.server_port = server_port
        self.us_name = us_name
        self.us_password = us_password

    def __enter__(self) -> smtplib.SMTP_SSL:
        try:
            # Using SMTP_SSL instead of SMTP with starttls for Mail.ru
            self.box = smtplib.SMTP_SSL(self.server_address, self.server_port)
            self.box.login(self.us_name, self.us_password)
            return self.box
        except Exception as e:
            logging.error(f"SMTP connection error: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logging.error(f"SMTP error occurred: {exc_val}")  
        try:
            self.box.quit()
        except Exception as e:
            logging.error(f"Error during SMTP exit: {e}")

class EmailCommunicator:
    def __init__(self, env_path="./data/env.json"): 
        io = Utils()
        env = io.load_json(env_path)
        self.emailAddress = env["email"]["address"]
        self.emailPassword = env["email"]["password"]
        self.emailSMTP = env["email"]["smtp"]
        self.emailIMAP = env["email"]["imap"]
        self.my_address = None
        # Добавляем хранение информации о последних командах для улучшенного ACK
        self.last_commands = {}  # Словарь для хранения информации о последних отправленных командах
        # Добавляем счетчик для индексации широковещательных сообщений
        self.broadcast_index = 0  # Счетчик для индексации широковещательных сообщений
        self.processed_broadcast_indexes = set()  # Множество для хранения обработанных индексов
        logging.info("EmailCommunicator initialized with no address")

    def set_my_address(self, address):
        """
        Устанавливает адрес данного компьютера для фильтрации сообщений
        """
        # Проверяем, что address не None и имеет валидный формат
        if address is not None and isinstance(address, str):
            # Дополнительная проверка формата адреса (должен быть x.x.x)
            addr_parts = address.split('.')
            if len(addr_parts) == 3 and all(part.isdigit() for part in addr_parts):
                self.my_address = address
                logging.info(f"Set computer address to: {address}")
            else:
                logging.error(f"Invalid address format (not x.x.x): {address}")
        else:
            if address is None:
                # Если передали None, это сброс адреса - разрешаем для совместимости
                self.my_address = None
                logging.info("Reset computer address to None")
            else:
                logging.error(f"Invalid address type provided to set_my_address: {type(address)}")

    def send(self, command: str | None, address: str, flag: str, log_message: str):
        """
        This method send command to another computer.
        If flag is IC, store command information for ACK tracking
        """
        import socket
        
        # Формируем тему письма, для широковещательных сообщений добавляем индекс
        if address == "255.255.255":
            # Увеличиваем счетчик индекса для широковещательных сообщений
            self.broadcast_index += 1
            # Добавляем индекс в адрес для широковещательных сообщений
            subject = f"0.0.0:{address}#{self.broadcast_index}:{flag}"
            logging.info(f"Broadcasting message with index #{self.broadcast_index}")
        else:
            subject = f"0.0.0:{address}:{flag}"
        
        message = f"From: {self.emailAddress}\nTo: {self.emailAddress}\nSubject: {subject}\n\n{log_message}(|||){compile_command(flag, command)}"
        
        # Сохраняем информацию о команде для последующего отслеживания ACK, если это команда (IC)
        if flag == "IC" and address != "0.0.0":  # Не отслеживаем команды, отправленные на сервер
            # Сохраняем информацию с идентификатором компьютера-получателя
            self.last_commands[address] = {
                "command": command,
                "timestamp": self.import_time().time(),
                "ack_received": False
            }
            logging.info(f"Tracking IC command '{command}' sent to {address} for ACK confirmation")
        
        try:
            with SMTPServerConnection(self.emailSMTP["host"], self.emailSMTP["port"], self.emailAddress, self.emailPassword) as box:
                box.sendmail(
                    self.emailAddress, self.emailAddress, message
                )
                logging.info(f"Email sent successfully to {self.emailAddress} with flag {flag} and address {address}.")
                
                # Если это ACK сообщение для IC команды, добавляем дополнительный log для уведомления
                if flag == "ACK" and "Command" in log_message and "acknowledged by" in log_message:
                    logging.info(f"📬 ACK sent: {log_message}")
                
        except Exception as e:
            logging.error(f"Error sending email: {e}")
            
    # Helper function for time import to avoid circular imports
    def import_time(self):
        import time
        return time

    def check_for_messages(self) -> bool:
        """
        Проверяет наличие сообщений в почтовом ящике, включая как прочитанные, так и непрочитанные.
        """
        try:
            with IMAPServerConnection(self.emailIMAP["host"], self.emailIMAP["port"], self.emailAddress, self.emailPassword) as mail:
                # List all available mailboxes to see the correct encoding
                resp, mailboxes = mail.list()
                
                # Use INBOX/ToMyself for Mail.ru
                mail.select("INBOX/ToMyself")
                
                # Изменено: ищем ВСЕ сообщения, а не только непрочитанные
                _, data = mail.search(None, "ALL")
                mail_ids = data[0]
                id_list = mail_ids.split()
                logging.debug(f"Total message IDs in INBOX/ToMyself: {id_list}")
                return bool(id_list)
        except Exception as e:
            logging.error(f"Error in check_for_messages: {e}")
            return False
        
    def create_imap_connection(self):
        """
        Создает прямое подключение к IMAP серверу без автоматической обработки сообщений.
        Это позволяет серверу исследовать сообщения, не помечая их автоматически как прочитанные.
        """
        return IMAPServerConnection(
            self.emailIMAP["host"], 
            self.emailIMAP["port"], 
            self.emailAddress, 
            self.emailPassword
        )
    
    def parse_email_message(self, raw_email):
        """
        Парсит email-сообщение и возвращает адрес, флаг и команду без пометки сообщения как прочитанное.
        
        Возвращает кортеж (address, flag, command) или None в случае ошибки.
        """
        try:
            raw_email_string = raw_email.decode("utf-8")
            email_message = email.message_from_string(raw_email_string)
            
            # Получаем содержимое письма
            payload = str(email_message.get_payload())
            logging.debug(f"Email payload: {payload}")
            
            # Получаем заголовки письма
            subject = email_message.get('Subject')
            logging.debug(f"Email subject: {subject}")
            
            # Разбор заголовка для получения адреса и флага
            address = "0.0.0"  # Значение по умолчанию
            flag = "IND"       # Значение по умолчанию
            broadcast_index = 0  # Значение по умолчанию
            
            # Parse subject to get address and flag (expected format: address:flag)
            if subject and ':' in subject:
                parts = subject.split(':')
                if len(parts) >= 3:
                    # Извлекаем адрес и проверяем, содержит ли он индекс (для широковещательных сообщений)
                    raw_address = parts[1].strip()
                    if '#' in raw_address and raw_address.startswith("255.255.255"):
                        # Широковещательное сообщение с индексом
                        address_parts = raw_address.split('#')
                        address = address_parts[0]  # 255.255.255
                        broadcast_index = int(address_parts[1]) if len(address_parts) > 1 and address_parts[1].isdigit() else 0
                        logging.info(f"Detected broadcast message with index #{broadcast_index}")
                    else:
                        # Обычное сообщение без индекса
                        address = raw_address
                        broadcast_index = 0
                    
                    flag = parts[2].strip()
                else:
                    address = "0.0.0"
                    flag = "IND"  # Default flag
                    broadcast_index = 0
            else:
                address = "0.0.0"
                flag = "IND"  # Default flag
                broadcast_index = 0
            
            # Извлечение команды из содержимого письма
            command = None
            
            # Случай двойного IND::::
            if "IND::::IND::::" in payload:
                command = payload.split("IND::::IND::::")[1].strip()
                flag = "IND"
                logging.debug(f"Detected double IND pattern, extracted command: {command}")
            # Обычный случай с разделителем (|||)
            elif "(|||)" in payload:
                raw_email_parts = payload.split("(|||)")
                log_message = raw_email_parts[0]
                
                if len(raw_email_parts) > 1:
                    command_part = raw_email_parts[1]
                    
                    # Извлекаем флаг и команду
                    if "::::" in command_part:
                        parsed_flag = command_part.split("::::")[0]
                        if parsed_flag:
                            flag = parsed_flag
                        
                        if len(command_part.split("::::")) > 1:
                            encoded_command = command_part.split("::::")[1]
                            
                            # Декодируем команду из base64, если она имеет флаг IC или IR
                            if flag in ["IC", "IR"] and encoded_command != "None":
                                try:
                                    command_bytes = base64.b64decode(encoded_command)
                                    command = command_bytes.decode('utf-8')
                                    logging.debug(f"Decoded base64 {flag} command: {command}")
                                except Exception as e:
                                    logging.error(f"Error decoding base64 message: {e}")
                                    command = encoded_command  # Возвращаем закодированную команду в случае ошибки
                            else:
                                command = encoded_command
                        else:
                            command = ""
                    else:
                        command = command_part
                else:
                    command = log_message
            else:
                command = payload
            
            logging.debug(f"Parsed email - Address: {address}, Flag: {flag}, Command: {command}")
            return address, flag, command
            
        except Exception as e:
            logging.error(f"Error parsing email message: {e}")
            return None

    def receive(self):
        id = Identifier()
        try:
            with IMAPServerConnection(self.emailIMAP["host"], self.emailIMAP["port"], self.emailAddress, self.emailPassword) as mail:
                # Use INBOX/ToMyself for Mail.ru
                mail.select("INBOX/ToMyself")
                
                # Изменено: ищем ВСЕ сообщения, а не только непрочитанные
                _, data = mail.search(None, "ALL")
                mail_ids = data[0]
                id_list = mail_ids.split()
                logging.debug(f"All message IDs: {id_list}")
                if not id_list:
                    return 0, 0
                    
                latest_email_id = id_list[-1]
                _, data = mail.fetch(latest_email_id, "(RFC822)")
                raw_email = data[0][1]
                raw_email_string = raw_email.decode("utf-8")
                email_message = email.message_from_string(raw_email_string)
                try:
                    # Get the email payload
                    payload = str(email_message.get_payload())
                    logging.debug(f"Email payload: {payload}")
                    
                    # Get subject from email headers
                    subject = email_message.get('Subject')
                    logging.debug(f"Email subject: {subject}")
                    
                    # Parse subject to get address and flag (expected format: address:flag)
                    address = "0.0.0"  # Значение по умолчанию
                    flag = "IND"       # Значение по умолчанию
                    broadcast_index = 0  # Значение по умолчанию
                    
                    if subject and ':' in subject:
                        parts = subject.split(':')
                        if len(parts) >= 3:
                            # Извлекаем адрес и проверяем, содержит ли он индекс (для широковещательных сообщений)
                            raw_address = parts[1].strip()
                            if '#' in raw_address and raw_address.startswith("255.255.255"):
                                # Широковещательное сообщение с индексом
                                address_parts = raw_address.split('#')
                                address = address_parts[0]  # 255.255.255
                                broadcast_index = int(address_parts[1]) if len(address_parts) > 1 and address_parts[1].isdigit() else 0
                                logging.info(f"Detected broadcast message with index #{broadcast_index}")
                            else:
                                # Обычное сообщение без индекса
                                address = raw_address
                                broadcast_index = 0
                            
                            flag = parts[2].strip()
                        else:
                            address = "0.0.0"
                            flag = "IND"  # Default flag
                            broadcast_index = 0
                    else:
                        address = "0.0.0"
                        flag = "IND"  # Default flag
                        broadcast_index = 0
                    
                    # Извлечь содержимое письма для случая двойного IND::::
                    if "IND::::IND::::" in payload:
                        # Особый случай двойного IND в сообщении
                        command = payload.split("IND::::IND::::")[1].strip()
                        flag = "IND"
                        logging.debug(f"Detected double IND pattern, extracted command: {command}")
                    # Обычная обработка для других случаев
                    elif "(|||)" in payload:
                        raw_email_parts = payload.split("(|||)")
                        log_message = raw_email_parts[0]
                        
                        if len(raw_email_parts) > 1:
                            command_part = raw_email_parts[1]
                            
                            # Extract flag and actual command
                            if "::::" in command_part:
                                parsed_flag = command_part.split("::::")[0]
                                if parsed_flag:
                                    flag = parsed_flag
                                
                                if len(command_part.split("::::")) > 1:
                                    encoded_command = command_part.split("::::")[1]
                                    
                                    # Декодируем команду из base64, если она имеет флаг IC или IR
                                    if flag in ["IC", "IR"] and encoded_command != "None":
                                        try:
                                            command_bytes = base64.b64decode(encoded_command)
                                            command = command_bytes.decode('utf-8')
                                            logging.debug(f"Decoded base64 {flag} command: {command}")
                                        except Exception as e:
                                            logging.error(f"Error decoding base64 message: {e}")
                                            command = encoded_command  # Возвращаем закодированную команду в случае ошибки
                                    else:
                                        command = encoded_command
                                else:
                                    command = ""
                            else:
                                command = command_part
                        else:
                            command = log_message
                    else:
                        command = payload
                    
                    logging.debug(f"Processed email - Subject: {subject}, Address: {address}, Flag: {flag}, Command: {command}")
                    result = 0, 0  # Default return value
                    
                    # Определяем, запущен ли скрипт в режиме сервера
                    import sys
                    is_server_mode = len(sys.argv) > 1 and sys.argv[1] == "server"
                    
                    # Process based on flag
                    if flag == "IND" and is_server_mode:  # Только сервер должен обрабатывать IND запросы
                        try:
                            # Прямая обработка команды для случая с флагом IND
                            logging.debug(f"Processing IND command in server mode: '{command}'")
                            
                            # Для обработки формата "hostname, OS"
                            if ", " in command:
                                name, os_info = command.split(", ", 1)
                                logging.debug(f"Parsed name: '{name}', OS: '{os_info}'")
                            else:
                                name = command
                                os_info = "unknown"
                                logging.debug(f"Could only parse name: '{name}', OS set to unknown")
                            
                            logging.info(f"Computer info - Name: {name}, OS: {os_info}")
                            
                            # Генерация адреса
                            address = id.generate_address(
                                {
                                    "os": os_info,
                                    "name": name
                                }
                            )
                            
                            # Отправка ответа
                            logging.info(f"Generated address {address} for {name}")
                            self.send(
                                f"{address}, {name}",
                                "255.255.255",
                                "INF",
                                "Address generated"
                            )
                            
                            # Изменено: удаляем сообщение вместо пометки прочитанным
                            mail.store(latest_email_id, "+FLAGS", "\\Deleted")
                            mail.expunge()
                            logging.info(f"📮 Server deleted IND request after processing")
                            return result
                        except Exception as e:
                            logging.error(f"Error in IND processing: {str(e)}")
                    elif flag == "IND" and not is_server_mode:
                        # В режиме suboard мы просто логируем получение сообщения, но не генерируем адрес
                        logging.debug(f"Received IND flag in suboard mode, ignoring address generation")
                    elif flag == "EDCN" and is_server_mode:
                        id.remove_address(address)
                    elif flag in ["IR", "ERR", "ACK"]:  # Добавляем ACK в список флагов для специальной обработки
                        result = command, flag
                    # Важное детальное логирование
                    logging.info(f"Current mode: {'SERVER' if is_server_mode else 'SUBOARD'}")
                    logging.info(f"My address setting: {self.my_address}")
                    logging.info(f"Message address: {address}")
                    logging.info(f"Message flag: {flag}")
                    
                    # НОВАЯ ЛОГИКА: Определяем, является ли сообщение адресованным нам
                    # и нужно ли его обрабатывать
                    should_process = False
                    
                    if is_server_mode:
                        # Сервер обрабатывает сообщения, адресованные ему (0.0.0)
                        # или сообщения INF (которые мы уже обработали выше)
                        # Также сервер обрабатывает ACK сообщения
                        should_process = (address == "0.0.0" and flag != "IND") or flag == "ACK"
                        logging.info(f"Server checking message: address={address}, flag={flag}, should_process={should_process}")
                    else:
                        # Клиент в режиме suboard
                        if self.my_address and address:
                            # Клиент обрабатывает только сообщения, адресованные ему лично
                            # или широковещательные (255.255.255)
                            should_process = (address == self.my_address or address == "255.255.255")
                            logging.info(f"Client with address {self.my_address} checking message: address={address}, should_process={should_process}")
                        else:
                            # Если адрес клиента еще не установлен, обрабатываем только INF сообщения (для получения адреса)
                            should_process = (flag == "INF")
                            logging.info(f"Client without address checking message: flag={flag}, should_process={should_process}")
                    
                    # КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Для команд IC не удаляем сообщение,
                    # а возвращаем его для выполнения в initiate_suboard(), но помечаем ID сообщения
                    if should_process:
                        # Выполняем дополнительную обработку сообщения, если необходимо
                        if flag == "INF" and not is_server_mode:
                            # Особая обработка для клиента, получающего свой адрес
                            if ", " in str(command):
                                potential_address, computer_name = str(command).split(", ", 1)
                                import socket
                                if computer_name.strip() == socket.gethostname():
                                    # Устанавливаем наш адрес
                                    self.set_my_address(potential_address.strip())
                            
                            # Удаляем сообщение INF после обработки
                            mail.store(latest_email_id, "+FLAGS", "\\Deleted")
                            mail.expunge()
                            logging.info(f"📮 Deleted INF message after processing")
                        elif flag == "IC" and not is_server_mode:
                            # Для сообщений с командами (IC) в режиме suboard
                            # НЕ удаляем сообщение здесь, а возвращаем его для выполнения
                            # в функции initiate_suboard
                            logging.info(f"📩 Found command to execute: {command}")
                            
                            # Сохраняем ID сообщения для последующего удаления после выполнения команды
                            # Создаем кортеж (команда, ID сообщения) для возврата
                            result = (command, flag, latest_email_id)
                            
                            # Сообщение будет удалено после выполнения команды в initiate_suboard
                            return result
                        elif flag == "ACK" and is_server_mode:
                            # Для сообщений с подтверждением (ACK) в режиме сервера
                            # Возвращаем сообщение для обработки в initiate_server
                            logging.info(f"📩 Found ACK message: {command}")
                            
                            # После обработки удаляем ACK сообщение
                            mail.store(latest_email_id, "+FLAGS", "\\Deleted")
                            mail.expunge()
                            logging.info(f"📮 Deleted ACK message after processing")
                            
                            # Возвращаем команду и флаг для обработки
                            return command, flag
                        else:
                            # Проверяем, является ли сообщение широковещательным (255.255.255)
                            # Если да, проверяем индекс и обрабатываем только новые сообщения
                            if address == "255.255.255":
                                # Для широковещательных сообщений проверяем индекс
                                if broadcast_index > 0:
                                    # Если индекс уже обработан, пропускаем сообщение
                                    if broadcast_index in self.processed_broadcast_indexes:
                                        logging.info(f"📩 Skipping already processed broadcast message with index #{broadcast_index}")
                                        # Оставляем сообщение в почтовом ящике для обработки другими получателями
                                        return 0, 0
                                    else:
                                        # Сообщение с новым индексом, обрабатываем его
                                        logging.info(f"📬 Processing new broadcast message with index #{broadcast_index}")
                                        # Добавляем индекс в множество обработанных
                                        self.processed_broadcast_indexes.add(broadcast_index)
                                        
                                        # Просто возвращаем результат обработки, но не удаляем сообщение
                                        if flag == "IC" and not is_server_mode:
                                            # Для команд в режиме подчиненного узла
                                            return (command, flag, latest_email_id)
                                        else:
                                            # Для других типов сообщений
                                            return command, flag
                                else:
                                    # Старый формат без индекса (для обратной совместимости)
                                    logging.info(f"📬 Processing broadcast message without index (old format)")
                                    
                                    # Добавляем проверку Message-ID письма, чтобы не обрабатывать одно и то же письмо дважды
                                    message_id = email_message.get('Message-ID', 'no-id')
                                    if message_id != 'no-id' and message_id in self.processed_broadcast_indexes:
                                        logging.info(f"📩 Skipping already processed broadcast message with Message-ID: {message_id}")
                                        # Оставляем сообщение в почтовом ящике для обработки другими получателями
                                        return 0, 0
                                    else:
                                        # Сохраняем Message-ID в множество обработанных
                                        if message_id != 'no-id':
                                            self.processed_broadcast_indexes.add(message_id)
                                            logging.info(f"Adding Message-ID to processed set: {message_id}")
                                        
                                        # Просто возвращаем результат обработки, но не удаляем сообщение
                                        if flag == "IC" and not is_server_mode:
                                            # Для команд в режиме подчиненного узла
                                            return (command, flag, latest_email_id)
                                        else:
                                            # Для других типов сообщений
                                            return command, flag
                            else:
                                # Все остальные сообщения просто удаляем после обработки
                                mail.store(latest_email_id, "+FLAGS", "\\Deleted")
                                mail.expunge()
                                logging.info(f"📮 Deleted message after processing: address={address}, flag={flag}")
                    else:
                        # Если сообщение НЕ адресовано нам, оставляем его в почтовом ящике
                        logging.info(f"📪 Left message in mailbox: address={address}, flag={flag} (not addressed to us)")
                    
                    if flag == "IC" and should_process and not is_server_mode:
                        # Если это команда и она адресована нам, возвращаем её
                        return command, flag
                    else:
                        # В других случаях возвращаем обычный результат
                        return result
                    
                except Exception as e:
                    logging.error(f"Error processing email: {e}")
                    # НЕ помечаем и не удаляем сообщение при ошибке
                    logging.warning(f"Not touching email due to processing error")
                    return 0, 0
        except Exception as e:
            logging.error(f"Error in receive method: {e}")
            return 0, 0
