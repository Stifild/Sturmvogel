package utils

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// Utils предоставляет функции для работы с файлами
type Utils struct{}

// LoadJSON загружает данные из JSON файла в структуру
func (u *Utils) LoadJSON(path string, v interface{}) error {
	// Убедимся, что директория существует
	dir := filepath.Dir(path)
	if _, err := os.Stat(dir); os.IsNotExist(err) {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
	}

	// Проверяем существование файла
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()

	// Декодируем JSON
	decoder := json.NewDecoder(file)
	return decoder.Decode(v)
}

// SaveJSON сохраняет структуру в JSON файл
func (u *Utils) SaveJSON(path string, v interface{}) error {
	// Убедимся, что директория существует
	dir := filepath.Dir(path)
	if _, err := os.Stat(dir); os.IsNotExist(err) {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
	}

	// Создаем или перезаписываем файл
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	// Кодируем структуру в JSON с отступами для читаемости
	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	return encoder.Encode(v)
}