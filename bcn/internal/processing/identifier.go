package processing

import (
	"fmt"
	"strconv"
	"strings"
	"sync"

	"github.com/stifild/sturmvogel/bcn/internal/utils"
)

// Identifier отвечает за генерацию и управление адресами компьютеров
type Identifier struct {
	twmcdPath string
	bcncd     utils.BCNCD
	mu        sync.Mutex
}

// NewIdentifier создает новый экземпляр Identifier
func NewIdentifier(twmcdPath string) *Identifier {
	return &Identifier{
		twmcdPath: twmcdPath,
		bcncd:     make(utils.BCNCD),
	}
}

// LoadBCNCD загружает словарь компьютеров из файла
func (id *Identifier) LoadBCNCD() error {
	id.mu.Lock()
	defer id.mu.Unlock()

	utilsObj := &utils.Utils{}
	return utilsObj.LoadJSON(id.twmcdPath, &id.bcncd)
}

// SaveBCNCD сохраняет словарь компьютеров в файл
func (id *Identifier) SaveBCNCD() error {
	id.mu.Lock()
	defer id.mu.Unlock()

	utilsObj := &utils.Utils{}
	return utilsObj.SaveJSON(id.twmcdPath, id.bcncd)
}

// GetComputerByAddress возвращает информацию о компьютере по его адресу
func (id *Identifier) GetComputerByAddress(address string) (string, string, bool) {
	id.mu.Lock()
	defer id.mu.Unlock()

	if computer, ok := id.bcncd[address]; ok {
		return computer.Name, computer.OS, true
	}
	return "", "", false
}

// AddComputer добавляет новый компьютер в словарь и возвращает его адрес
func (id *Identifier) AddComputer(name, osInfo string) (string, error) {
	id.mu.Lock()
	defer id.mu.Unlock()

	// Генерируем новый адрес
	address, err := id.generateAddress()
	if err != nil {
		return "", err
	}

	// Добавляем компьютер в словарь
	id.bcncd[address] = struct {
		Name string `json:"name"`
		OS   string `json:"os"`
	}{
		Name: name,
		OS:   osInfo,
	}

	// Сохраняем обновленный словарь
	utilsObj := &utils.Utils{}
	if err := utilsObj.SaveJSON(id.twmcdPath, id.bcncd); err != nil {
		return "", err
	}

	return address, nil
}

// generateAddress генерирует новый уникальный адрес
func (id *Identifier) generateAddress() (string, error) {
	// Находим максимальный адрес
	var maxA, maxB, maxC int
	for address := range id.bcncd {
		parts := strings.Split(address, ".")
		if len(parts) != 3 {
			continue
		}

		a, _ := strconv.Atoi(parts[0])
		b, _ := strconv.Atoi(parts[1])
		c, _ := strconv.Atoi(parts[2])

		if a > maxA || (a == maxA && b > maxB) || (a == maxA && b == maxB && c > maxC) {
			maxA, maxB, maxC = a, b, c
		}
	}

	// Увеличиваем последнее число
	maxC++
	if maxC > 255 {
		maxC = 0
		maxB++
		if maxB > 255 {
			maxB = 0
			maxA++
			if maxA > 255 {
				return "", fmt.Errorf("address space exhausted")
			}
		}
	}

	// Серверу всегда присваивается адрес 0.0.0
	if maxA == 0 && maxB == 0 && maxC == 0 {
		maxC = 1 // Пропускаем 0.0.0, так как это адрес сервера
	}

	return fmt.Sprintf("%d.%d.%d", maxA, maxB, maxC), nil
}

// GetAllComputers возвращает словарь всех компьютеров
func (id *Identifier) GetAllComputers() utils.BCNCD {
	id.mu.Lock()
	defer id.mu.Unlock()

	result := make(utils.BCNCD)
	for k, v := range id.bcncd {
		result[k] = v
	}
	return result
}

// RemoveComputer удаляет компьютер из словаря
func (id *Identifier) RemoveComputer(address string) error {
	id.mu.Lock()
	defer id.mu.Unlock()

	if _, ok := id.bcncd[address]; !ok {
		return fmt.Errorf("computer with address %s not found", address)
	}

	delete(id.bcncd, address)

	utilsObj := &utils.Utils{}
	return utilsObj.SaveJSON(id.twmcdPath, id.bcncd)
}