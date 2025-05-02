package utils

// Config представляет собой структуру для конфигурационного файла
type Config struct {
	MainUserID int    `json:"MAIN_USER_ID"`
	BotToken   string `json:"BOT_TOKEN"`
	Email      struct {
		Address  string `json:"address"`
		Password string `json:"password"`
		SMTP     struct {
			Host string `json:"host"`
			Port int    `json:"port"`
		} `json:"smtp"`
		IMAP struct {
			Host string `json:"host"`
			Port int    `json:"port"`
		} `json:"imap"`
	} `json:"email"`
}

// BCNCD представляет словарь компьютеров в сети BCN
type BCNCD map[string]struct {
	Name string `json:"name"`
	OS   string `json:"os"`
}