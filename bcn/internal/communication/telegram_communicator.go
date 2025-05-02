package communication

import (
	"fmt"
	"log"
	"strconv"
	"strings"
	"sync"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/stifild/stormvogel/bcn/internal/processing"
	"github.com/stifild/stormvogel/bcn/internal/utils"
)

// TelegramCommunicator представляет собой модуль для работы с Telegram-ботом
type TelegramCommunicator struct {
	bot           *tgbotapi.BotAPI
	config        *utils.Config
	identifier    *processing.Identifier
	emailCom      *EmailCommunicator
	activeDialogs map[int64]struct {
		Name    string
		Address string
	}
	botCommands map[string]string
	mu          sync.Mutex
	stopCh      chan struct{}
}

// NewTelegramCommunicator создает новый экземпляр TelegramCommunicator
func NewTelegramCommunicator(config *utils.Config, emailCom *EmailCommunicator, identifier *processing.Identifier) (*TelegramCommunicator, error) {
	bot, err := tgbotapi.NewBotAPI(config.BotToken)
	if err != nil {
		return nil, fmt.Errorf("error creating Telegram bot: %w", err)
	}

	tc := &TelegramCommunicator{
		bot:        bot,
		config:     config,
		identifier: identifier,
		emailCom:   emailCom,
		activeDialogs: make(map[int64]struct {
			Name    string
			Address string
		}),
		botCommands: map[string]string{
			"/start":  "Начать работу с ботом",
			"/help":   "Показать список доступных команд",
			"/list":   "Показать список доступных устройств",
			"/send":   "Отправить команду на устройство (формат: /send [device_name] [command])",
			"/dialog": "Начать диалог с устройством (формат: /dialog [device_name])",
			"/exit":   "Выйти из режима диалога с устройством",
		},
		stopCh: make(chan struct{}),
	}

	log.Println("Telegram bot initialized successfully")
	return tc, nil
}

// Start запускает Telegram-бота в отдельной горутине
func (tc *TelegramCommunicator) Start() {
	log.Println("Starting Telegram bot in a goroutine")

	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60

	updates := tc.bot.GetUpdatesChan(u)

	go func() {
		for {
			select {
			case update := <-updates:
				tc.handleUpdate(update)
			case <-tc.stopCh:
				tc.bot.StopReceivingUpdates()
				log.Println("Telegram bot stopped")
				return
			}
		}
	}()
}

// Stop останавливает Telegram-бота
func (tc *TelegramCommunicator) Stop() {
	log.Println("Stopping Telegram bot")
	close(tc.stopCh)
}

// handleUpdate обрабатывает обновления от Telegram
func (tc *TelegramCommunicator) handleUpdate(update tgbotapi.Update) {
	if update.Message == nil {
		return
	}

	// Проверяем, имеет ли пользователь доступ
	if update.Message.From.ID != int64(tc.config.MainUserID) {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "⚠️ У вас нет прав для использования этого бота.\nОбратитесь к администратору для получения доступа.")
		tc.bot.Send(msg)
		return
	}

	// Обрабатываем команды
	if update.Message.IsCommand() {
		tc.handleCommand(update.Message)
		return
	}

	// Обрабатываем текстовые сообщения
	tc.handleTextMessage(update.Message)
}

// handleCommand обрабатывает команды Telegram
func (tc *TelegramCommunicator) handleCommand(message *tgbotapi.Message) {
	switch message.Command() {
	case "start":
		tc.handleStart(message)
	case "help":
		tc.handleHelp(message)
	case "list":
		tc.handleList(message)
	case "send":
		tc.handleSend(message)
	case "dialog":
		tc.handleDialog(message)
	case "exit":
		tc.handleExit(message)
	default:
		// Неизвестная команда
		tc.handleUnknownCommand(message)
	}
}

// handleStart обрабатывает команду /start
func (tc *TelegramCommunicator) handleStart(message *tgbotapi.Message) {
	text := fmt.Sprintf("👋 Привет, %s!\n\nЯ бот для удаленного управления устройствами. Используй /help для просмотра доступных команд.", message.From.FirstName)
	msg := tgbotapi.NewMessage(message.Chat.ID, text)
	tc.bot.Send(msg)
}

// handleHelp обрабатывает команду /help
func (tc *TelegramCommunicator) handleHelp(message *tgbotapi.Message) {
	helpText := "📌 *Доступные команды:*\n\n"
	for cmd, desc := range tc.botCommands {
		helpText += fmt.Sprintf("• `%s` - %s\n", cmd, desc)
	}

	helpText += "\n💡 Пример использования команды send:\n`/send my_pc reboot`"

	msg := tgbotapi.NewMessage(message.Chat.ID, helpText)
	msg.ParseMode = "Markdown"
	tc.bot.Send(msg)
}

// handleList обрабатывает команду /list
func (tc *TelegramCommunicator) handleList(message *tgbotapi.Message) {
	// Получаем список компьютеров
	computers := tc.identifier.GetAllComputers()

	if len(computers) == 0 {
		msg := tgbotapi.NewMessage(message.Chat.ID, "❌ Устройства не найдены.")
		tc.bot.Send(msg)
		return
	}

	devicesText := "📱 *Доступные устройства:*\n\n"
	for address, data := range computers {
		devicesText += fmt.Sprintf("• *%s*\n  └ Адрес: `%s`\n", data.Name, address)
	}

	devicesText += "\nДля отправки команды используйте:\n`/send [device_name] [command]`"

	msg := tgbotapi.NewMessage(message.Chat.ID, devicesText)
	msg.ParseMode = "Markdown"
	tc.bot.Send(msg)
}

// extractArguments извлекает аргументы из команды
func (tc *TelegramCommunicator) extractArguments(text string) string {
	parts := strings.SplitN(text, " ", 2)
	if len(parts) < 2 {
		return ""
	}
	return parts[1]
}

// handleSend обрабатывает команду /send
func (tc *TelegramCommunicator) handleSend(message *tgbotapi.Message) {
	rawCommand := tc.extractArguments(message.Text)
	if rawCommand == "" || !strings.Contains(rawCommand, " ") {
		text := "⚠️ *Неверный формат команды*\n\n" +
			"Правильный формат: `/send [device_name] [command]`\n\n" +
			"Пример: `/send my_pc reboot`\n\n" +
			"Используйте `/list` для просмотра доступных устройств."
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
		return
	}

	parts := strings.SplitN(rawCommand, " ", 2)
	computerName := parts[0]
	command := parts[1]

	// Получаем список компьютеров
	computers := tc.identifier.GetAllComputers()

	// Ищем компьютер по имени
	var found bool
	var deviceAddress string
	for address, data := range computers {
		if data.Name == computerName {
			found = true
			deviceAddress = address
			break
		}
	}

	if !found {
		// Формируем список доступных устройств
		var availableDevices []string
		for _, data := range computers {
			availableDevices = append(availableDevices, fmt.Sprintf("`%s`", data.Name))
		}

		devicesList := "нет доступных устройств"
		if len(availableDevices) > 0 {
			devicesList = strings.Join(availableDevices, ", ")
		}

		text := fmt.Sprintf("❌ *Ошибка:* Устройство `%s` не найдено!\n\n"+
			"*Доступные устройства:*\n%s\n\n"+
			"Используйте `/list` для получения подробной информации.",
			computerName, devicesList)
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
		return
	}

	// Отправляем команду
	err := tc.emailCom.Send(command, deviceAddress, "IC", fmt.Sprintf("Listen %s! I want you to do %s", computerName, command))
	if err != nil {
		text := fmt.Sprintf("❌ *Ошибка:* Не удалось отправить команду. %s", err.Error())
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
		return
	}

	text := fmt.Sprintf("✅ Команда успешно отправлена!\n\n"+
		"• Устройство: *%s*\n"+
		"• Адрес: `%s`\n"+
		"• Команда: `%s`",
		computerName, deviceAddress, command)
	msg := tgbotapi.NewMessage(message.Chat.ID, text)
	msg.ParseMode = "Markdown"
	tc.bot.Send(msg)
}

// handleDialog обрабатывает команду /dialog
func (tc *TelegramCommunicator) handleDialog(message *tgbotapi.Message) {
	deviceName := tc.extractArguments(message.Text)
	if deviceName == "" {
		text := "⚠️ *Неверный формат команды*\n\n" +
			"Правильный формат: `/dialog [device_name]`\n\n" +
			"Пример: `/dialog my_pc`\n\n" +
			"Используйте `/list` для просмотра доступных устройств."
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
		return
	}

	// Получаем список компьютеров
	computers := tc.identifier.GetAllComputers()

	// Ищем компьютер по имени
	var found bool
	var deviceAddress string
	for address, data := range computers {
		if data.Name == deviceName {
			found = true
			deviceAddress = address
			break
		}
	}

	if !found {
		// Формируем список доступных устройств
		var availableDevices []string
		for _, data := range computers {
			availableDevices = append(availableDevices, fmt.Sprintf("`%s`", data.Name))
		}

		devicesList := "нет доступных устройств"
		if len(availableDevices) > 0 {
			devicesList = strings.Join(availableDevices, ", ")
		}

		text := fmt.Sprintf("❌ *Ошибка:* Устройство `%s` не найдено!\n\n"+
			"*Доступные устройства:*\n%s\n\n"+
			"Используйте `/list` для получения подробной информации.",
			deviceName, devicesList)
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
		return
	}

	// Сохраняем информацию о начатом диалоге
	tc.mu.Lock()
	tc.activeDialogs[message.From.ID] = struct {
		Name    string
		Address string
	}{
		Name:    deviceName,
		Address: deviceAddress,
	}
	tc.mu.Unlock()

	text := fmt.Sprintf("✅ *Диалог с устройством начат!*\n\n"+
		"• Устройство: *%s*\n"+
		"• Адрес: `%s`\n\n"+
		"Теперь все сообщения будут отправляться на это устройство.\n"+
		"Для выхода из режима диалога используйте команду `/exit`.",
		deviceName, deviceAddress)
	msg := tgbotapi.NewMessage(message.Chat.ID, text)
	msg.ParseMode = "Markdown"
	tc.bot.Send(msg)
}

// handleExit обрабатывает команду /exit
func (tc *TelegramCommunicator) handleExit(message *tgbotapi.Message) {
	tc.mu.Lock()
	dialog, ok := tc.activeDialogs[message.From.ID]
	if ok {
		delete(tc.activeDialogs, message.From.ID)
	}
	tc.mu.Unlock()

	if ok {
		text := fmt.Sprintf("✅ Диалог с устройством *%s* завершен.\n\n"+
			"Вы вернулись в обычный режим.", dialog.Name)
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
	} else {
		text := "ℹ️ Вы не находитесь в режиме диалога с устройством."
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
	}
}

// handleUnknownCommand обрабатывает неизвестные команды
func (tc *TelegramCommunicator) handleUnknownCommand(message *tgbotapi.Message) {
	text := "❓ Не понимаю вашу команду. Используйте следующие команды:\n\n" +
		"• `/help` - список всех команд\n" +
		"• `/list` - список всех устройств\n" +
		"• `/send [device_name] [command]` - отправка команды\n" +
		"• `/dialog [device_name]` - начать диалог с устройством\n" +
		"• `/exit` - выйти из режима диалога"
	msg := tgbotapi.NewMessage(message.Chat.ID, text)
	msg.ParseMode = "Markdown"
	tc.bot.Send(msg)
}

// handleTextMessage обрабатывает текстовые сообщения (не команды)
func (tc *TelegramCommunicator) handleTextMessage(message *tgbotapi.Message) {
	tc.mu.Lock()
	dialog, inDialog := tc.activeDialogs[message.From.ID]
	tc.mu.Unlock()

	if inDialog {
		// Пользователь в режиме диалога, отправляем команду на устройство
		command := message.Text
		err := tc.emailCom.Send(command, dialog.Address, "IC", fmt.Sprintf("Listen %s! I want you to do %s", dialog.Name, command))
		if err != nil {
			text := fmt.Sprintf("❌ *Ошибка:* Не удалось отправить команду. %s", err.Error())
			msg := tgbotapi.NewMessage(message.Chat.ID, text)
			msg.ParseMode = "Markdown"
			tc.bot.Send(msg)
			return
		}

		text := fmt.Sprintf("✅ Команда отправлена на устройство *%s*:\n`%s`", dialog.Name, command)
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
	} else {
		// Пользователь не в режиме диалога, показываем подсказку
		text := "ℹ️ Вы не в режиме диалога с устройством.\n\n" +
			"Используйте:\n" +
			"• `/dialog [device_name]` - для начала диалога с устройством\n" +
			"• `/send [device_name] [command]` - для отправки команды\n" +
			"• `/help` - список всех команд"
		msg := tgbotapi.NewMessage(message.Chat.ID, text)
		msg.ParseMode = "Markdown"
		tc.bot.Send(msg)
	}
}

// SendMessage отправляет сообщение пользователю
func (tc *TelegramCommunicator) SendMessage(text string) error {
	userID, err := strconv.ParseInt(fmt.Sprintf("%d", tc.config.MainUserID), 10, 64)
	if err != nil {
		return fmt.Errorf("error parsing user ID: %w", err)
	}

	msg := tgbotapi.NewMessage(userID, text)
	_, err = tc.bot.Send(msg)
	return err
}