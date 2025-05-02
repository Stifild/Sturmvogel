package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/stifild/stormvogel/bcn/internal/communication"
	"github.com/stifild/stormvogel/bcn/internal/processing"
	"github.com/stifild/stormvogel/bcn/internal/utils"
)

const (
	envPath     = "./data/env.json"
	twmcdPath   = "./data/twmcd.json"
	serverDelay = 3500 * time.Millisecond
)

func main() {
	// Настраиваем логирование
	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Println("BCN Server инициализация...")

	// Проверяем аргументы командной строки
	if len(os.Args) < 2 {
		log.Fatalf("Используйте: %s [server|suboard]", os.Args[0])
	}

	switch os.Args[1] {
	case "server":
		initiateServer()
	case "suboard":
		initiateSuboard()
	default:
		log.Fatalf("Недопустимый аргумент. Используйте 'server' или 'suboard'")
	}
}

func initiateServer() {
	log.Println("Инициализация сервера BCN...")

	// Инициализация утилит
	utilsObj := &utils.Utils{}

	// Создаем чистый файл twmcd.json перед запуском сервера
	emptyTwmcd := map[string]struct {
		Name string `json:"name"`
		OS   string `json:"os"`
	}{
		"0.0.0": {
			Name: "server",
			OS:   "",
		},
	}

	// Перезаписываем файл twmcd.json
	if err := utilsObj.SaveJSON(twmcdPath, emptyTwmcd); err != nil {
		log.Fatalf("Ошибка при создании twmcd.json: %v", err)
	}
	log.Println("Файл twmcd.json пересоздан с чистым состоянием")

	// Загружаем конфигурацию
	config := &utils.Config{}
	if err := utilsObj.LoadJSON(envPath, config); err != nil {
		log.Fatalf("Ошибка загрузки конфигурации: %v", err)
	}

	// Инициализация идентификатора
	identifier := processing.NewIdentifier(twmcdPath)
	if err := identifier.LoadBCNCD(); err != nil {
		log.Printf("Ошибка загрузки BCNCD: %v. Будет использоваться пустой словарь", err)
	}

	// Инициализация email-коммуникатора
	emailCom, err := communication.NewEmailCommunicator(envPath)
	if err != nil {
		log.Fatalf("Ошибка инициализации EmailCommunicator: %v", err)
	}
	emailCom.SetMyAddress("0.0.0") // Сервер всегда имеет адрес 0.0.0

	// Инициализация Telegram-бота
	telegramBot, err := communication.NewTelegramCommunicator(config, emailCom, identifier)
	if err != nil {
		log.Fatalf("Ошибка инициализации TelegramCommunicator: %v", err)
	}

	// Запуск Telegram-бота
	telegramBot.Start()
	log.Println("Telegram-бот запущен в отдельной горутине")

	// Обработка сигналов для корректного завершения
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)
	
	// Создаем канал для завершения цикла проверки email
	done := make(chan struct{})
	
	// Запускаем цикл проверки email в отдельной горутине
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		emailCheckLoop(emailCom, telegramBot, config, done)
	}()
	
	// Ожидаем сигнала для завершения
	sig := <-sigs
	log.Printf("Получен сигнал %v, завершение работы...", sig)
	
	// Отправляем сигнал для завершения горутины проверки email
	close(done)
	
	// Останавливаем Telegram-бота
	telegramBot.Stop()
	
	// Отправляем сообщение о завершении работы сервера
	err = emailCom.Send("", "255.255.255", "EDCN", "Server is shutting down")
	if err != nil {
		log.Printf("Ошибка отправки сообщения о завершении: %v", err)
	}
	
	// Ожидаем завершения горутины проверки email
	wg.Wait()
	log.Println("Сервер BCN остановлен")
}

func emailCheckLoop(emailCom *communication.EmailCommunicator, telegramBot *communication.TelegramCommunicator, config *utils.Config, done chan struct{}) {
	log.Println("Запущен цикл проверки email")
	
	// Создаём идентификатор для обработки IND-запросов
	identifier := processing.NewIdentifier(twmcdPath)
	if err := identifier.LoadBCNCD(); err != nil {
		log.Printf("Ошибка загрузки BCNCD в цикле проверки email: %v. Будет использоваться пустой словарь", err)
	}
	
	for {
		select {
		case <-done:
			log.Println("Цикл проверки email остановлен")
			return
		default:
			// Проверяем наличие новых сообщений
			hasMessages, err := emailCom.CheckForMessages()
			if err != nil {
				log.Printf("Ошибка проверки наличия сообщений: %v", err)
				time.Sleep(serverDelay)
				continue
			}
			
			if hasMessages {
				// Получаем и обрабатываем сообщения
				receive, flag, err := emailCom.Receive()
				if err != nil {
					log.Printf("Ошибка получения сообщений: %v", err)
					time.Sleep(serverDelay)
					continue
				}
				
				// Обрабатываем сообщения с разными флагами
				switch flag {
				case "IR", "ERR":
					log.Printf("Получено сообщение с флагом: %s, содержимое: %v", flag, receive)
					
					// Отправляем сообщение в Telegram
					var message string
					if flag == "ERR" {
						message = fmt.Sprintf("Flag: %s, Receive: %v", flag, receive)
					} else {
						message = fmt.Sprintf("Ответ:\n%v", receive)
					}
					
					err = telegramBot.SendMessage(message)
					if err != nil {
						log.Printf("Ошибка отправки сообщения в Telegram: %v", err)
					} else {
						log.Printf("Сообщение с флагом %s отправлено в Telegram", flag)
					}
				
				case "ACK":
					log.Printf("Получено ACK сообщение: %v", receive)
					
					// Обрабатываем ACK сообщение
					if receiveStr, ok := receive.(string); ok && receiveStr != "" {
						// Улучшенная обработка ACK сообщений
						if strings.Contains(receiveStr, "Command") && strings.Contains(receiveStr, "acknowledged by") {
							// Стандартное ACK сообщение для IC команд
							command := extractBetween(receiveStr, "'", "'")
							computer := ""
							if parts := strings.Split(receiveStr, "acknowledged by "); len(parts) > 1 {
								computer = parts[1]
							}
							
							message := fmt.Sprintf("✅ ACK: Компьютер '%s' подтвердил получение команды '%s'", computer, command)
							err = telegramBot.SendMessage(message)
							if err != nil {
								log.Printf("Ошибка отправки ACK уведомления в Telegram: %v", err)
							}
						} else if strings.Contains(receiveStr, "Address") && strings.Contains(receiveStr, "acknowledged by") {
							// ACK сообщение для адреса
							address := ""
							if parts := strings.Split(receiveStr, "Address "); len(parts) > 1 {
								address = strings.Split(parts[1], " acknowledged")[0]
							}
							
							computer := ""
							if parts := strings.Split(receiveStr, "acknowledged by "); len(parts) > 1 {
								computer = parts[1]
							}
							
							message := fmt.Sprintf("📍 ACK: Компьютер '%s' подтвердил получение адреса '%s'", computer, address)
							err = telegramBot.SendMessage(message)
							if err != nil {
								log.Printf("Ошибка отправки ACK уведомления для адреса в Telegram: %v", err)
							}
						} else {
							// Общее ACK сообщение
							message := fmt.Sprintf("🔔 ACK: %s", receiveStr)
							err = telegramBot.SendMessage(message)
							if err != nil {
								log.Printf("Ошибка отправки общего ACK уведомления в Telegram: %v", err)
							}
						}
					}
					
				case "IND":
					// Обрабатываем запрос на идентификацию
					log.Printf("Получен запрос на идентификацию: %v", receive)
					if receiveStr, ok := receive.(string); ok && receiveStr != "" {
						address, err := handleIndRequest(emailCom, identifier, receiveStr)
						if err != nil {
							log.Printf("Ошибка обработки запроса на идентификацию: %v", err)
							
							// Отправляем уведомление об ошибке в Telegram
							err = telegramBot.SendMessage(fmt.Sprintf("❌ Ошибка обработки запроса на идентификацию: %v", err))
							if err != nil {
								log.Printf("Ошибка отправки уведомления об ошибке в Telegram: %v", err)
							}
						} else {
							log.Printf("Успешно обработан запрос на идентификацию. Выдан адрес: %s", address)
							
							// Отправляем уведомление в Telegram
							message := fmt.Sprintf("🆕 Новое устройство запросило подключение:\nИмя: %s\nВыдан адрес: %s", receiveStr, address)
							err = telegramBot.SendMessage(message)
							if err != nil {
								log.Printf("Ошибка отправки уведомления о новом устройстве в Telegram: %v", err)
							}
						}
					}
					
				case "FIN":
					// Обрабатываем запрос на отключение от сети
					log.Printf("Получен запрос на отключение от сети: %v", receive)
					
					// Отправляем уведомление в Telegram
					if receiveStr, ok := receive.(string); ok {
						message := fmt.Sprintf("🔌 Устройство отключилось от сети: %s", receiveStr)
						err = telegramBot.SendMessage(message)
						if err != nil {
							log.Printf("Ошибка отправки уведомления об отключении в Telegram: %v", err)
						}
					}
				}
			}
			
			// Ждем перед следующей проверкой
			time.Sleep(serverDelay)
		}
	}
}

// extractBetween извлекает текст между двумя строками
func extractBetween(s, start, end string) string {
	if !strings.Contains(s, start) || !strings.Contains(s, end) {
		return ""
	}
	
	startIndex := strings.Index(s, start) + len(start)
	endIndex := strings.Index(s[startIndex:], end)
	if endIndex == -1 {
		return ""
	}
	
	return s[startIndex : startIndex+endIndex]
}

// handleIndRequest обрабатывает запросы на идентификацию
func handleIndRequest(emailCom *communication.EmailCommunicator, identifier *processing.Identifier, command string) (string, error) {
	// Для обработки формата "hostname, OS"
	var name, osInfo string
	if strings.Contains(command, ", ") {
		parts := strings.SplitN(command, ", ", 2)
		name = parts[0]
		osInfo = parts[1]
		log.Printf("Разобрано имя: '%s', ОС: '%s'", name, osInfo)
	} else {
		name = command
		osInfo = "unknown"
		log.Printf("Удалось получить только имя: '%s', ОС установлена как unknown", name)
	}

	log.Printf("Информация о компьютере - Имя: %s, ОС: %s", name, osInfo)

	// Генерация адреса
	address, err := identifier.AddComputer(name, osInfo)
	if err != nil {
		return "", fmt.Errorf("ошибка генерации адреса: %w", err)
	}

	// Сохраняем обновленный словарь
	if err := identifier.SaveBCNCD(); err != nil {
		return "", fmt.Errorf("ошибка сохранения BCNCD: %w", err)
	}

	log.Printf("Сгенерирован адрес %s для %s", address, name)
	
	// Отправляем информационное сообщение
	msg := fmt.Sprintf("%s, %s", address, name)
	err = emailCom.Send(
		msg,
		"255.255.255",
		"INF",
		"Address generated",
	)
	if err != nil {
		return "", fmt.Errorf("ошибка отправки INF-сообщения: %w", err)
	}

	return address, nil
}

func initiateSuboard() {
	// Реализация будет создана в отдельном файле
}