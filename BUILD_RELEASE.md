# Инструкция по сборке релиза

## Подготовка окружения

### 1. Установите зависимости

#### Python зависимости:
```bash
pip install -r requirements-build.txt
```

#### Node.js зависимости:
```bash
cd frontend
npm install
cd ..
```

## Сборка

### Linux/macOS:

```bash
chmod +x build.sh
./build.sh
```

### Windows:

```bash
build.bat
```

## Результат

После успешной сборки:
- Исполняемый файл будет в папке `dist/`
- **Linux/macOS**: `dist/CashMachine`
- **Windows**: `dist/CashMachine.exe`
