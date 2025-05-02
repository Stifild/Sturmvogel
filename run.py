import sys
from BCN.BCNInit import initiate_server, initiate_suboard

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Запускаем графический интерфейс, если нет аргументов
        from gui import BCNControlPanel, QApplication
        app = QApplication(sys.argv)
        window = BCNControlPanel()
        window.show()
        sys.exit(app.exec())

    if sys.argv[1] == "server":
        initiate_server()
    elif sys.argv[1] == "suboard":
        initiate_suboard()
    else:
        print("Invalid argument. Use 'server' or 'suboard'.")
