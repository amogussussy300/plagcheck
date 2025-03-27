# plagcheck api

## как начать

### 1. клонировать
```
git clone https://github.com/amogussussy300/plagcheck.git
cd plagcheck
```

### 2. установить зависимости
```
pip install -r requirements.txt
```
### 3. запустить
```
waitress-serve.exe --host=0.0.0.0 --port=5000 --threads=8 application:app
```
### 4. запустить EXAMPLE.py
чтобы понять как работает апи

## что за параметры
| Флаг         | Значение      | Описание      |
|--------------|---------------|---------------|
| `--host`     | `0.0.0.0`     | ip-адрес      |
| `--port`     | `5000`        | порт          |
| `--threads`  | `8`           | число потоков |

---

## проверить
после запуска сервер будет доступен по адресу:  
```
http://localhost:5000
```
или  
```
http://введённыйipадрес:введённыйпорт
```
---

> **примечание**  
> для Windows используй `.exe` версию Waitress.  
> на linux/macos команда будет:  
> `waitress-serve --host=0.0.0.0 --port=5000 --threads=8 application:app`