package communication

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"net/mail"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/emersion/go-imap"
	"github.com/emersion/go-imap/client"
	"github.com/emersion/go-message/charset"
	"github.com/emersion/go-sasl"
	"github.com/stifild/sturmvogel/bcn/internal/utils"
	"net/smtp"
)

// EmailCommunicator представляет собой класс для работы с электронной почтой
type EmailCommunicator struct {
	emailAddress  string
	emailPassword string
	emailSMTP     struct {
		Host string
		Port int
	}
	emailIMAP struct {
		Host string
		Port int
	}
	myAddress    string
	lastCommands map[string]struct {
		Command     string
		Timestamp   time.Time
		AckReceived bool
	}
	mu sync.Mutex
}

// NewEmailCommunicator создаёт новый экземпляр EmailCommunicator
func NewEmailCommunicator(envPath string) (*EmailCommunicator, error) {
	// Если путь не абсолютный, преобразуем его
	if !filepath.IsAbs(envPath) {
		dir, err := os.Getwd()
		if err != nil {
			return nil, fmt.Errorf("error getting current directory: %w", err)
		}
		envPath = filepath.Join(dir, envPath)
	}

	utilsObj := &utils.Utils{}
	config := &utils.Config{}

	if err := utilsObj.LoadJSON(envPath, config); err != nil {
		return nil, fmt.Errorf("error loading config: %w", err)
	}

	ec := &EmailCommunicator{
		emailAddress:  config.Email.Address,
		emailPassword: config.Email.Password,
		lastCommands:  make(map[string]struct{ Command string; Timestamp time.Time; AckReceived bool }),
	}

	ec.emailSMTP.Host = config.Email.SMTP.Host
	ec.emailSMTP.Port = config.Email.SMTP.Port
	ec.emailIMAP.Host = config.Email.IMAP.Host
	ec.emailIMAP.Port = config.Email.IMAP.Port

	return ec, nil
}

// SetMyAddress устанавливает адрес текущего компьютера
func (ec *EmailCommunicator) SetMyAddress(address string) {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	// Проверяем формат адреса (должен быть x.x.x)
	if address != "" {
		addrParts := strings.Split(address, ".")
		if len(addrParts) == 3 {
			// Проверяем, что все части являются числами
			validParts := true
			for _, part := range addrParts {
				if _, err := fmt.Sscanf(part, "%d", new(int)); err != nil {
					validParts = false
					break
				}
			}
			if validParts {
				ec.myAddress = address
				fmt.Printf("Set computer address to: %s\n", address)
				return
			}
		}
		fmt.Printf("Invalid address format (not x.x.x): %s\n", address)
	} else {
		// Если передали пустую строку, сбрасываем адрес
		ec.myAddress = ""
		fmt.Println("Reset computer address to empty")
	}
}

// GetMyAddress возвращает текущий адрес компьютера
func (ec *EmailCommunicator) GetMyAddress() string {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	return ec.myAddress
}

// compileCommand кодирует команду в соответствии с протоколом BCN
func compileCommand(flag string, command string) string {
	if command == "" {
		return fmt.Sprintf("%s::::None", flag)
	}
	
	// Кодируем команду в base64, если это IC или IR команда
	if flag == "IC" || flag == "IR" {
		encodedCmd := base64.StdEncoding.EncodeToString([]byte(command))
		return fmt.Sprintf("%s::::%s", flag, encodedCmd)
	}
	
	return fmt.Sprintf("%s::::%s", flag, command)
}

// Send отправляет сообщение через SMTP
func (ec *EmailCommunicator) Send(command string, address string, flag string, logMessage string) error {
	ec.mu.Lock()
	
	// Сохраняем информацию о команде для отслеживания ACK
	if flag == "IC" && address != "0.0.0" {
		ec.lastCommands[address] = struct {
			Command     string
			Timestamp   time.Time
			AckReceived bool
		}{
			Command:     command,
			Timestamp:   time.Now(),
			AckReceived: false,
		}
		fmt.Printf("Tracking IC command '%s' sent to %s for ACK confirmation\n", command, address)
	}
	
	ec.mu.Unlock()

	// Формируем заголовки и тело письма
	from := mail.Address{Address: ec.emailAddress}
	to := mail.Address{Address: ec.emailAddress}
	
	// Формирует уникальное отправление с BoundaryID
	senderAddr := "0.0.0"
	if ec.myAddress != "" {
		senderAddr = ec.myAddress
	}
	
	subject := fmt.Sprintf("%s:%s:%s", senderAddr, address, flag)
	compiledCmd := compileCommand(flag, command)
	body := fmt.Sprintf("%s(|||)%s", logMessage, compiledCmd)
	
	// Формируем письмо в формате RFC 822
	headers := make(map[string]string)
	headers["From"] = from.String()
	headers["To"] = to.String()
	headers["Subject"] = subject
	headers["MIME-Version"] = "1.0"
	headers["Content-Type"] = "text/plain; charset=\"utf-8\""
	
	message := ""
	for k, v := range headers {
		message += fmt.Sprintf("%s: %s\r\n", k, v)
	}
	message += "\r\n" + body
	
	// Отправляем письмо
	auth := sasl.NewPlainClient("", ec.emailAddress, ec.emailPassword)
	addr := fmt.Sprintf("%s:%d", ec.emailSMTP.Host, ec.emailSMTP.Port)
	
	err := smtp.SendMail(addr, auth, ec.emailAddress, []string{ec.emailAddress}, []byte(message))
	if err != nil {
		return fmt.Errorf("error sending email: %w", err)
	}
	
	fmt.Printf("Email sent successfully to %s with flag %s and address %s\n", ec.emailAddress, flag, address)
	
	// Логируем отправку ACK-сообщения
	if flag == "ACK" && strings.Contains(logMessage, "Command") && strings.Contains(logMessage, "acknowledged by") {
		fmt.Printf("📬 ACK sent: %s\n", logMessage)
	}
	
	return nil
}

// CheckForMessages проверяет наличие сообщений в почтовом ящике
func (ec *EmailCommunicator) CheckForMessages() (bool, error) {
	// Инициализируем функцию для обработки кодировок
	charset.RegisterEncoding("utf-8", charset.UTF8)
	
	// Подключаемся к IMAP серверу
	addr := fmt.Sprintf("%s:%d", ec.emailIMAP.Host, ec.emailIMAP.Port)
	c, err := client.DialTLS(addr, nil)
	if err != nil {
		return false, fmt.Errorf("error connecting to IMAP server: %w", err)
	}
	defer c.Logout()
	
	// Авторизуемся
	if err := c.Login(ec.emailAddress, ec.emailPassword); err != nil {
		return false, fmt.Errorf("error logging in to IMAP server: %w", err)
	}
	
	// Выбираем папку "INBOX/ToMyself"
	_, err = c.Select("INBOX/ToMyself", false)
	if err != nil {
		return false, fmt.Errorf("error selecting mailbox: %w", err)
	}
	
	// Ищем все сообщения
	criteria := imap.NewSearchCriteria()
	criteria.WithoutFlags = []string{imap.DeletedFlag}
	ids, err := c.Search(criteria)
	if err != nil {
		return false, fmt.Errorf("error searching for messages: %w", err)
	}
	
	return len(ids) > 0, nil
}

// ParseEmailMessage разбирает email-сообщение и возвращает адрес, флаг и команду
func (ec *EmailCommunicator) ParseEmailMessage(msg *imap.Message) (string, string, string, error) {
	if msg == nil || len(msg.Body) == 0 {
		return "", "", "", fmt.Errorf("empty message")
	}
	
	var subject string
	for _, header := range msg.Envelope.Subject {
		subject += string(header)
	}
	
	// Разбор заголовка для получения адреса и флага
	address := "0.0.0" // Значение по умолчанию
	flag := "IND"      // Значение по умолчанию
	
	if subject != "" && strings.Contains(subject, ":") {
		parts := strings.Split(subject, ":")
		if len(parts) >= 3 {
			address = strings.TrimSpace(parts[1])
			flag = strings.TrimSpace(parts[2])
		}
	}
	
	// Извлечение содержимого письма
	var bodyBuf bytes.Buffer
	for _, part := range msg.Body {
		_, err := bodyBuf.ReadFrom(part)
		if err != nil {
			continue
		}
	}
	
	payload := bodyBuf.String()
	var command string
	
	// Случай двойного IND::::
	if strings.Contains(payload, "IND::::IND::::") {
		parts := strings.Split(payload, "IND::::IND::::")
		if len(parts) > 1 {
			command = strings.TrimSpace(parts[1])
			flag = "IND"
		}
	} else if strings.Contains(payload, "(|||)") {
		// Обычный случай с разделителем (|||)
		parts := strings.Split(payload, "(|||)")
		logMessage := parts[0]
		
		if len(parts) > 1 {
			commandPart := parts[1]
			
			// Извлекаем флаг и команду
			if strings.Contains(commandPart, "::::") {
				cmdParts := strings.Split(commandPart, "::::")
				if len(cmdParts) > 0 && cmdParts[0] != "" {
					parsedFlag := cmdParts[0]
					flag = parsedFlag
				}
				
				if len(cmdParts) > 1 {
					encodedCommand := cmdParts[1]
					
					// Декодируем команду из base64, если она имеет флаг IC или IR
					if (flag == "IC" || flag == "IR") && encodedCommand != "None" {
						decodedBytes, err := base64.StdEncoding.DecodeString(encodedCommand)
						if err == nil {
							command = string(decodedBytes)
						} else {
							command = encodedCommand // Возвращаем закодированную команду в случае ошибки
						}
					} else {
						command = encodedCommand
					}
				} else {
					command = ""
				}
			} else {
				command = commandPart
			}
		} else {
			command = logMessage
		}
	} else {
		command = payload
	}
	
	return address, flag, command, nil
}

// Receive получает и обрабатывает сообщения из почтового ящика
func (ec *EmailCommunicator) Receive() (interface{}, string, error) {
	// Инициализируем функцию для обработки кодировок
	charset.RegisterEncoding("utf-8", charset.UTF8)
	
	// Подключаемся к IMAP серверу
	addr := fmt.Sprintf("%s:%d", ec.emailIMAP.Host, ec.emailIMAP.Port)
	c, err := client.DialTLS(addr, nil)
	if err != nil {
		return nil, "", fmt.Errorf("error connecting to IMAP server: %w", err)
	}
	defer c.Logout()
	
	// Авторизуемся
	if err := c.Login(ec.emailAddress, ec.emailPassword); err != nil {
		return nil, "", fmt.Errorf("error logging in to IMAP server: %w", err)
	}
	
	// Выбираем папку "INBOX/ToMyself"
	_, err = c.Select("INBOX/ToMyself", false)
	if err != nil {
		return nil, "", fmt.Errorf("error selecting mailbox: %w", err)
	}
	
	// Ищем все сообщения
	criteria := imap.NewSearchCriteria()
	criteria.WithoutFlags = []string{imap.DeletedFlag}
	ids, err := c.Search(criteria)
	if err != nil {
		return nil, "", fmt.Errorf("error searching for messages: %w", err)
	}
	
	if len(ids) == 0 {
		return 0, "0", nil
	}
	
	// Берем последнее сообщение
	latestID := ids[len(ids)-1]
	seqSet := new(imap.SeqSet)
	seqSet.AddNum(latestID)
	
	// Получаем полное сообщение
	section := &imap.BodySectionName{}
	items := []imap.FetchItem{imap.FetchEnvelope, section.FetchItem()}
	messages := make(chan *imap.Message, 1)
	err = c.Fetch(seqSet, items, messages)
	if err != nil {
		return nil, "", fmt.Errorf("error fetching message: %w", err)
	}
	
	msg := <-messages
	if msg == nil {
		return nil, "", fmt.Errorf("no message received")
	}
	
	// Парсим сообщение
	address, flag, command, err := ec.ParseEmailMessage(msg)
	if err != nil {
		return nil, "", fmt.Errorf("error parsing message: %w", err)
	}
	
	// Определяем, является ли скрипт сервером 
	isServerMode := ec.myAddress == "0.0.0"
	
	// Обрабатываем сообщение на основе флага
	switch flag {
	case "IND":
		if isServerMode {
			// Обработка IND запросов на сервере будет реализована в другом месте
			
			// Помечаем сообщение как удаленное
			delItems := imap.FormatFlagsOp(imap.AddFlags, true, []string{imap.DeletedFlag})
			err = c.Store(seqSet, delItems, nil)
			if err != nil {
				fmt.Printf("Error marking message as deleted: %v\n", err)
			}
			
			// Удаляем помеченные сообщения
			if err := c.Expunge(nil); err != nil {
				fmt.Printf("Error expunging messages: %v\n", err)
			}
			
			fmt.Println("📮 Server deleted IND request after processing")
		}
		return command, flag, nil
		
	case "INF":
		if !isServerMode {
			// Обработка INF сообщений на клиенте
			if strings.Contains(command, ", ") {
				parts := strings.Split(command, ", ")
				potentialAddress := strings.TrimSpace(parts[0])
				computerName := strings.TrimSpace(parts[1])
				
				hostname, err := os.Hostname()
				if err == nil && computerName == hostname {
					// Устанавливаем наш адрес
					ec.SetMyAddress(potentialAddress)
				}
			}
			
			// Помечаем сообщение как удаленное
			delItems := imap.FormatFlagsOp(imap.AddFlags, true, []string{imap.DeletedFlag})
			err = c.Store(seqSet, delItems, nil)
			if err != nil {
				fmt.Printf("Error marking message as deleted: %v\n", err)
			}
			
			// Удаляем помеченные сообщения
			if err := c.Expunge(nil); err != nil {
				fmt.Printf("Error expunging messages: %v\n", err)
			}
			
			fmt.Println("📮 Deleted INF message after processing")
		}
		return command, flag, nil
		
	case "IC":
		if !isServerMode {
			// Для сообщений с командами в режиме клиента
			fmt.Printf("📩 Found command to execute: %s\n", command)
			
			// Возвращаем кортеж (команда, флаг, ID сообщения)
			return []interface{}{command, flag, latestID}, flag, nil
		}
		
	case "ACK":
		if isServerMode {
			// Обработка ACK сообщений на сервере
			fmt.Printf("📩 Found ACK message: %s\n", command)
			
			// Помечаем сообщение как удаленное
			delItems := imap.FormatFlagsOp(imap.AddFlags, true, []string{imap.DeletedFlag})
			err = c.Store(seqSet, delItems, nil)
			if err != nil {
				fmt.Printf("Error marking message as deleted: %v\n", err)
			}
			
			// Удаляем помеченные сообщения
			if err := c.Expunge(nil); err != nil {
				fmt.Printf("Error expunging messages: %v\n", err)
			}
			
			fmt.Println("📮 Deleted ACK message after processing")
		}
		
	case "IR", "ERR":
		// Помечаем сообщение как удаленное
		delItems := imap.FormatFlagsOp(imap.AddFlags, true, []string{imap.DeletedFlag})
		err = c.Store(seqSet, delItems, nil)
		if err != nil {
			fmt.Printf("Error marking message as deleted: %v\n", err)
		}
		
		// Удаляем помеченные сообщения
		if err := c.Expunge(nil); err != nil {
			fmt.Printf("Error expunging messages: %v\n", err)
		}
		
		fmt.Printf("📮 Deleted %s message after processing\n", flag)
	
	default:
		// Остальные сообщения оставляем в почтовом ящике
		fmt.Printf("📪 Left message with flag %s in mailbox\n", flag)
	}
	
	return command, flag, nil
}

// DeleteMessage удаляет сообщение с указанным ID
func (ec *EmailCommunicator) DeleteMessage(messageID uint32) error {
	// Подключаемся к IMAP серверу
	addr := fmt.Sprintf("%s:%d", ec.emailIMAP.Host, ec.emailIMAP.Port)
	c, err := client.DialTLS(addr, nil)
	if err != nil {
		return fmt.Errorf("error connecting to IMAP server: %w", err)
	}
	defer c.Logout()
	
	// Авторизуемся
	if err := c.Login(ec.emailAddress, ec.emailPassword); err != nil {
		return fmt.Errorf("error logging in to IMAP server: %w", err)
	}
	
	// Выбираем папку "INBOX/ToMyself"
	_, err = c.Select("INBOX/ToMyself", false)
	if err != nil {
		return fmt.Errorf("error selecting mailbox: %w", err)
	}
	
	// Создаем набор для указанного ID
	seqSet := new(imap.SeqSet)
	seqSet.AddNum(messageID)
	
	// Помечаем сообщение как удаленное
	delItems := imap.FormatFlagsOp(imap.AddFlags, true, []string{imap.DeletedFlag})
	err = c.Store(seqSet, delItems, nil)
	if err != nil {
		return fmt.Errorf("error marking message as deleted: %w", err)
	}
	
	// Удаляем помеченные сообщения
	if err := c.Expunge(nil); err != nil {
		return fmt.Errorf("error expunging messages: %w", err)
	}
	
	fmt.Printf("📮 Deleted message with ID %d\n", messageID)
	return nil
}