import sys
import os
import threading
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                            QHBoxLayout, QWidget, QTextEdit, QLabel, QGroupBox,
                            QDialog, QLineEdit, QFormLayout, QMessageBox, QCheckBox,
                            QSpinBox, QFileDialog)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt
from PyQt6.QtGui import QFont, QIcon
from BCN.BCNInit import initiate_server, initiate_suboard, stop_server, stop_suboard
from BCN.Proccesing.utils import Utils

class LogHandler(QObject):
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.buffer = []
        
    def emit(self, record):
        msg = f"{record.levelname}: {record.getMessage()}"
        self.buffer.append(msg)
        self.log_signal.emit(msg)

class ConfigWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Мастер конфигурации BCN")
        self.setMinimumWidth(400)
        self.utils = Utils()
        
        # Устанавливаем иконку для окна мастера конфигурации
        self.setWindowIcon(QIcon("ico.ico"))
        
        # Основной layout
        main_layout = QVBoxLayout()
        
        # Форма для ввода данных
        form_layout = QFormLayout()
        
        # Telegram секция
        telegram_group = QGroupBox("Telegram настройки")
        telegram_layout = QFormLayout()
        
        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("Ваш Telegram ID (в числовом формате)")
        telegram_layout.addRow("ID пользователя:", self.user_id_input)
        
        self.bot_token_input = QLineEdit()
        self.bot_token_input.setPlaceholderText("Токен от BotFather")
        telegram_layout.addRow("Токен бота:", self.bot_token_input)
        
        telegram_group.setLayout(telegram_layout)
        main_layout.addWidget(telegram_group)
        
        # Email секция
        email_group = QGroupBox("Email настройки")
        email_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Адрес электронной почты")
        email_layout.addRow("Email адрес:", self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль приложения")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        email_layout.addRow("Пароль:", self.password_input)
        
        # По умолчанию mail.ru
        self.smtp_host_input = QLineEdit("smtp.mail.ru")
        email_layout.addRow("SMTP хост:", self.smtp_host_input)
        
        self.smtp_port_input = QSpinBox()
        self.smtp_port_input.setRange(1, 65535)
        self.smtp_port_input.setValue(465)
        email_layout.addRow("SMTP порт:", self.smtp_port_input)
        
        self.imap_host_input = QLineEdit("imap.mail.ru")
        email_layout.addRow("IMAP хост:", self.imap_host_input)
        
        self.imap_port_input = QSpinBox()
        self.imap_port_input.setRange(1, 65535)
        self.imap_port_input.setValue(993)
        email_layout.addRow("IMAP порт:", self.imap_port_input)
        
        email_group.setLayout(email_layout)
        main_layout.addWidget(email_group)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_config)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        main_layout.addLayout(buttons_layout)
        
        # Установка layout
        self.setLayout(main_layout)
        
        # Загрузка существующей конфигурации, если она есть
        self.load_existing_config()
        
    def load_existing_config(self):
        """Загружает существующую конфигурацию, если она есть"""
        try:
            # Проверяем, существует ли директория data
            if not os.path.exists('./data'):
                os.makedirs('./data')
                
            config = self.utils.load_json("./data/env.json")
            if config:
                if "MAIN_USER_ID" in config:
                    self.user_id_input.setText(str(config["MAIN_USER_ID"]))
                if "BOT_TOKEN" in config:
                    self.bot_token_input.setText(config["BOT_TOKEN"])
                if "email" in config:
                    email_config = config["email"]
                    if "address" in email_config:
                        self.email_input.setText(email_config["address"])
                    if "password" in email_config:
                        self.password_input.setText(email_config["password"])
                    if "smtp" in email_config:
                        smtp = email_config["smtp"]
                        if "host" in smtp:
                            self.smtp_host_input.setText(smtp["host"])
                        if "port" in smtp:
                            self.smtp_port_input.setValue(smtp["port"])
                    if "imap" in email_config:
                        imap = email_config["imap"]
                        if "host" in imap:
                            self.imap_host_input.setText(imap["host"])
                        if "port" in imap:
                            self.imap_port_input.setValue(imap["port"])
        except Exception as e:
            print(f"Ошибка при загрузке конфигурации: {e}")
    
    def save_config(self):
        """Сохраняет конфигурацию в файл"""
        try:
            # Проверка обязательных полей email
            if not self.email_input.text() or not self.password_input.text():
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Пожалуйста, заполните обязательные поля email."
                )
                return
            
            # Проверка корректности ID пользователя (должно быть числом) только если поле заполнено
            user_id = None
            if self.user_id_input.text():
                try:
                    user_id = int(self.user_id_input.text())
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Ошибка",
                        "ID пользователя должен быть целым числом."
                    )
                    return
            
            # Формируем конфигурацию
            config = {
                "email": {
                    "address": self.email_input.text(),
                    "password": self.password_input.text(),
                    "smtp": {
                        "host": self.smtp_host_input.text(),
                        "port": self.smtp_port_input.value()
                    },
                    "imap": {
                        "host": self.imap_host_input.text(),
                        "port": self.imap_port_input.value()
                    }
                }
            }
            
            # Добавляем настройки Telegram только если они заполнены
            if user_id is not None:
                config["MAIN_USER_ID"] = user_id
                
            if self.bot_token_input.text():
                config["BOT_TOKEN"] = self.bot_token_input.text()
            
            # Показываем предупреждение, если настройки Telegram не заполнены
            if user_id is None or not self.bot_token_input.text():
                QMessageBox.warning(
                    self,
                    "Внимание",
                    "Настройки Telegram не заполнены. Запуск сервера BCN будет недоступен. "
                    "Вы сможете использовать только функции клиента (suboard)."
                )
            
            # Проверяем, существует ли директория data
            if not os.path.exists('./data'):
                os.makedirs('./data')
                
            # Сохраняем конфигурацию
            self.utils.save_json("./data/env.json", config)
            
            QMessageBox.information(
                self,
                "Успех",
                "Конфигурация успешно сохранена."
            )
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сохранить конфигурацию: {str(e)}"
            )

class BCNControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sturmvogel")
        self.setGeometry(100, 100, 800, 600)
        
        # Установка иконки приложения
        self.setWindowIcon(QIcon("ico.ico"))
        
        # Главный виджет и компоновка
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Заголовок
        title_label = QLabel("Sturmvogel")
        title_font = QFont("Arial", 16, QFont.Weight.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Панель управления сервером
        server_group = QGroupBox("Сервер")
        server_layout = QVBoxLayout()
        
        # Кнопки управления сервером
        server_buttons_layout = QHBoxLayout()
        self.start_server_btn = QPushButton("Запустить сервер")
        self.start_server_btn.clicked.connect(self.start_server)
        self.stop_server_btn = QPushButton("Остановить сервер")
        self.stop_server_btn.clicked.connect(self.stop_server)
        self.stop_server_btn.setEnabled(False)
        
        server_buttons_layout.addWidget(self.start_server_btn)
        server_buttons_layout.addWidget(self.stop_server_btn)
        server_layout.addLayout(server_buttons_layout)
        
        # Статус сервера
        self.server_status = QLabel("Статус: Не запущен")
        server_layout.addWidget(self.server_status)
        
        server_group.setLayout(server_layout)
        main_layout.addWidget(server_group)
        
        # Панель управления клиентом (suboard)
        client_group = QGroupBox("Клиент (Suboard)")
        client_layout = QVBoxLayout()
        
        # Кнопки управления клиентом
        client_buttons_layout = QHBoxLayout()
        self.start_client_btn = QPushButton("Запустить клиент")
        self.start_client_btn.clicked.connect(self.start_client)
        self.stop_client_btn = QPushButton("Остановить клиент")
        self.stop_client_btn.clicked.connect(self.stop_client)
        self.stop_client_btn.setEnabled(False)
        
        client_buttons_layout.addWidget(self.start_client_btn)
        client_buttons_layout.addWidget(self.stop_client_btn)
        client_layout.addLayout(client_buttons_layout)
        
        # Статус клиента
        self.client_status = QLabel("Статус: Не запущен")
        client_layout.addWidget(self.client_status)
        
        client_group.setLayout(client_layout)
        main_layout.addWidget(client_group)
        
        # Лог-окно
        log_group = QGroupBox("Лог")
        log_layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        # Кнопка запуска мастера конфигурации
        self.config_wizard_btn = QPushButton("Запустить мастер конфигурации")
        self.config_wizard_btn.clicked.connect(self.run_config_wizard)
        main_layout.addWidget(self.config_wizard_btn)
        
        # Установка главного лэйаута
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Переменные для хранения состояния
        self.server_thread = None
        self.client_thread = None
        self.server_running = False
        self.client_running = False
        
        # Настройка логирования
        self.setup_logging()
        
        # Таймер для обновления UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(500)  # Обновление каждые 500 мс
        
        # Проверяем наличие и правильность конфигурации
        QTimer.singleShot(100, self.check_config)
        
    def check_config(self):
        """Проверяет наличие и правильность конфигурационного файла"""
        utils = Utils()
        try:
            # Проверяем, существует ли директория data
            if not os.path.exists('./data'):
                self.append_log("Директория data не найдена, создаем...")
                os.makedirs('./data')
                self.append_log("Необходимо настроить конфигурацию. Запускаем мастер...")
                QTimer.singleShot(500, self.run_config_wizard)
                return
            
            # Проверяем существование env.json
            try:
                config = utils.load_json("./data/env.json")
                
                # Проверяем наличие всех необходимых полей
                config_valid = True
                email_valid = True
                
                if not config:
                    config_valid = False
                    email_valid = False
                    self.append_log("Файл конфигурации пуст. Запускаем мастер конфигурации...")
                else:
                    # Проверяем обязательные поля email
                    if "email" not in config:
                        config_valid = False
                        email_valid = False
                        self.append_log("В конфигурации отсутствуют настройки email")
                    else:
                        # Проверяем поля email
                        email_fields = ["address", "password", "smtp", "imap"]
                        for field in email_fields:
                            if field not in config["email"]:
                                config_valid = False
                                email_valid = False
                                self.append_log(f"В конфигурации отсутствует обязательное поле email.{field}")
                        
                        # Проверяем поля smtp и imap
                        if "smtp" in config["email"]:
                            if "host" not in config["email"]["smtp"] or "port" not in config["email"]["smtp"]:
                                config_valid = False
                                email_valid = False
                                self.append_log("В конфигурации отсутствуют настройки SMTP")
                        
                        if "imap" in config["email"]:
                            if "host" not in config["email"]["imap"] or "port" not in config["email"]["imap"]:
                                config_valid = False
                                email_valid = False
                                self.append_log("В конфигурации отсутствуют настройки IMAP")
                    
                    # Проверяем поля Telegram отдельно (они не обязательны для работы клиента)
                    if "MAIN_USER_ID" not in config or "BOT_TOKEN" not in config:
                        config_valid = False
                        self.append_log("В конфигурации отсутствуют настройки Telegram. Сервер будет недоступен.")
                
                # Запускаем мастер только если email-настройки неверны
                if not email_valid:
                    self.append_log("Email конфигурация неполная. Запускаем мастер...")
                    QTimer.singleShot(500, self.run_config_wizard)
                else:
                    if not config_valid:
                        self.append_log("Конфигурация проверена. Email настроен корректно, но телеграм настройки отсутствуют.")
                    else:
                        self.append_log("Конфигурация проверена и готова к работе!")
                    
            except Exception as e:
                self.append_log(f"Ошибка при проверке конфигурации: {str(e)}")
                QTimer.singleShot(500, self.run_config_wizard)
                
        except Exception as e:
            self.append_log(f"Ошибка при проверке конфигурации: {str(e)}")
    
    def setup_logging(self):
        import logging
        
        # Создаем обработчик для логирования в UI
        self.log_handler = LogHandler()
        self.log_handler.log_signal.connect(self.append_log)
        
        # Настраиваем корневой логгер
        logging.basicConfig(level=logging.INFO)
        root_logger = logging.getLogger()
        
        # Добавляем наш обработчик
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Добавляем обработчик для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Добавляем обработчик для вывода в GUI
        class UILogHandler(logging.Handler):
            def __init__(self, signal_fn):
                super().__init__()
                self.signal_fn = signal_fn
                
            def emit(self, record):
                msg = f"{record.asctime} - {record.levelname}: {record.getMessage()}"
                self.signal_fn(msg)
        
        ui_handler = UILogHandler(self.append_log)
        ui_handler.setLevel(logging.INFO)
        root_logger.addHandler(ui_handler)
        
        # Логируем запуск приложения
        logging.info("BCN Control Panel запущен")
    
    def append_log(self, message):
        """Добавить сообщение в лог-окно"""
        self.log_area.append(message)
        # Прокрутка вниз
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
    
    def update_ui(self):
        """Обновить интерфейс на основе состояния"""
        # Проверяем статус сервера
        if self.server_thread and self.server_thread.is_alive():
            if not self.server_running:
                self.server_running = True
                self.server_status.setText("Статус: Запущен")
                self.start_server_btn.setEnabled(False)
                self.stop_server_btn.setEnabled(True)
        else:
            if self.server_running:
                self.server_running = False
                self.server_status.setText("Статус: Не запущен")
                self.start_server_btn.setEnabled(True)
                self.stop_server_btn.setEnabled(False)
        
        # Проверяем статус клиента
        if self.client_thread and self.client_thread.is_alive():
            if not self.client_running:
                self.client_running = True
                self.client_status.setText("Статус: Запущен")
                self.start_client_btn.setEnabled(False)
                self.stop_client_btn.setEnabled(True)
        else:
            if self.client_running:
                self.client_running = False
                self.client_status.setText("Статус: Не запущен")
                self.start_client_btn.setEnabled(True)
                self.stop_client_btn.setEnabled(False)
    
    def start_server(self):
        """Запустить BCN сервер в отдельном потоке"""
        # Проверка наличия настроек Telegram перед запуском сервера
        utils = Utils()
        config = utils.load_json("./data/env.json")
        
        # Проверяем наличие настроек Telegram
        if "MAIN_USER_ID" not in config or "BOT_TOKEN" not in config:
            QMessageBox.critical(
                self,
                "Ошибка",
                "Невозможно запустить сервер: отсутствуют настройки Telegram. "
                "Пожалуйста, запустите мастер конфигурации и заполните поля Telegram."
            )
            return
        
        if not self.server_thread or not self.server_thread.is_alive():
            self.append_log("Запуск сервера...")
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
    
    def _run_server(self):
        """Функция для запуска сервера в отдельном потоке"""
        try:
            initiate_server()
        except Exception as e:
            self.append_log(f"Ошибка при запуске сервера: {str(e)}")
    
    def stop_server(self):
        """Остановить BCN сервер"""
        if self.server_running:
            self.append_log("Остановка сервера...")
            success = stop_server()
            
            # Принудительно прерываем поток сервера
            if self.server_thread and self.server_thread.is_alive():
                import ctypes
                thread_id = self.server_thread.ident
                if thread_id:
                    try:
                        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                            ctypes.c_long(thread_id),
                            ctypes.py_object(SystemExit)
                        )
                        if res > 1:
                            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                                ctypes.c_long(thread_id), 
                                None
                            )
                        self.append_log("Принудительное завершение потока сервера")
                    except Exception as e:
                        self.append_log(f"Ошибка при остановке потока сервера: {str(e)}")
            
            # Обновляем состояние UI немедленно
            self.server_running = False
            self.server_status.setText("Статус: Не запущен")
            self.start_server_btn.setEnabled(True)
            self.stop_server_btn.setEnabled(False)
            
            if success:
                self.append_log("Сервер успешно остановлен")
            else:
                self.append_log("Ошибка при остановке сервера")
    
    def start_client(self):
        """Запустить BCN клиент (suboard) в отдельном потоке"""
        if not self.client_thread or not self.client_thread.is_alive():
            self.append_log("Запуск клиента...")
            self.client_thread = threading.Thread(target=self._run_client, daemon=True)
            self.client_thread.start()
    
    def _run_client(self):
        """Функция для запуска клиента в отдельном потоке"""
        try:
            initiate_suboard()
        except Exception as e:
            self.append_log(f"Ошибка при запуске клиента: {str(e)}")
    
    def stop_client(self):
        """Остановить BCN клиент"""
        if self.client_running:
            self.append_log("Остановка клиента...")
            success = stop_suboard()
            if success:
                self.append_log("Клиент успешно остановлен")
            else:
                self.append_log("Ошибка при остановке клиента")
    
    def run_config_wizard(self):
        """Запустить мастер конфигурации"""
        self.append_log("Запуск мастера конфигурации...")
        wizard = ConfigWizard(self)
        wizard.exec()
    
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Попытка остановить сервер и клиент
        if self.server_running:
            self.stop_server()
        
        if self.client_running:
            self.stop_client()
        
        # Даем время на обработку остановки
        time.sleep(0.5)
        
        # Принимаем событие закрытия
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BCNControlPanel()
    window.show()
    sys.exit(app.exec())