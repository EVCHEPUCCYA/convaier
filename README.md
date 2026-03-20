# Convaier

Локальный AI-powered CI/CD конвейер для небольших команд разработки.

Convaier анализирует код, запускает линтеры, выполняет AI код-ревью, прогоняет тесты и деплоит Docker-контейнеры.

## Требования

- Python 3.10+
- Ollama для локального запуска LLM
- Git
- Docker (для этапов build/deploy)

## Установка

```bash
git clone <repo-url>
cd convaier
pip install -e .
```

Установите модель для Ollama:

```bash
ollama pull qwen2.5-coder:3b
```


## Быстрый старт

```bash
# Перейдите в ваш проект
cd /path/to/your/project

# Сгенерируйте конфиг
convaier init

# Отредактируйте convaier.yml под свой проект
# ...

# Проверьте подключение к Ollama
convaier check

# Запустите конвейер
convaier run
```

> Если команда `convaier` не найдена, используйте `python -m convaier` вместо неё.

## Команды CLI

| Команда | Описание |
|---------|----------|
| `convaier init` | Создать `convaier.yml` с примером конфигурации |
| `convaier check` | Проверить конфиг и подключение к Ollama |
| `convaier run` | Запустить конвейер |
| `convaier run --dry-run` | Показать этапы без выполнения |
| `convaier run -s lint,test` | Запустить только указанные этапы |
| `convaier run -c path.yml` | Использовать альтернативный конфиг |

Флаг `-v` (verbose) включает подробный вывод:

```bash
convaier -v run
```

## Конфигурация

Файл `convaier.yml` в корне проекта:

```yaml
project:
  name: my-app

ollama:
  host: http://localhost:11434   # адрес Ollama
  model: qwen2.5-coder:3b       # модель для AI-ревью
  timeout: 300                   # таймаут LLM-запроса (секунды)

pipeline:
  fail_fast: true                # остановить при первой ошибке
  stages:                        # этапы конвейера (по порядку)
    - commit
    - lint
    - review
    - test
    - build
    - deploy

stages:
  commit:
    diff_target: HEAD~1          # с чем сравнивать (по умолчанию: HEAD~1)

  lint:
    tools:                       # список линтеров
      - command: ruff check .
        name: ruff
      - command: mypy src/
        name: mypy
    fail_on_error: true          # считать ошибки линтера провалом

  review:
    focus:                       # на чём сфокусировать AI-ревью
      - security
      - performance
    max_files: 20                # максимум файлов для анализа
    max_diff_lines: 3000         # максимум строк diff

  test:
    command: pytest --tb=short -q

  build:
    dockerfile: Dockerfile
    image_name: my-app
    tag: latest

  deploy:
    compose_file: docker-compose.yml
    service: app

reports:
  output_dir: .convaier/reports  # куда сохранять отчёты
  formats:                       # форматы отчётов
    - markdown
    - json
```

## Этапы конвейера

### commit

Собирает git diff и список изменённых файлов. Это основа для последующих этапов.

- **diff_target** — с чем сравнивать (`HEAD~1`, `main`, конкретный коммит)

### lint

Запускает внешние линтеры и парсит их вывод.

- Поддерживает любые инструменты с выводом формата `file:line:col: message`
- Примеры: `ruff`, `mypy`, `flake8`, `pylint`

### review

AI-агент анализирует diff и содержимое файлов через Ollama.

- Агент получает статические данные (diff, файлы, результаты линтера)
- Может вызывать инструменты: `read_file`, `list_files`
- Возвращает комментарии с severity: `critical`, `warning`, `info`, `suggestion`

### test

Запускает тесты через указанную команду (по умолчанию `pytest`).

- Парсит вывод pytest для подсчёта passed/failed/skipped

### build

Собирает Docker-образ.

- Пропускается автоматически, если предыдущие этапы упали

### deploy

Запускает сервис через `docker compose up -d`.

- Пропускается, если build не прошёл

## Отчёты

После каждого запуска генерируются отчёты в `.convaier/reports/`:

- **Markdown**
- **JSON**

Пример Markdown-отчёта:

```
# Convaier Pipeline Report
**Project**: my-app | **Date**: 2026-03-19 17:30:00 | **Result**: PASSED

## Timings
- **commit**: 0.2s
- **review**: 120.5s

## Commit
- Changed files: 3

## Code Review (AI)
### `app.py:26` [critical]
> SQL injection: user input is interpolated directly into SQL query
```

## Архитектура

```
src/convaier/
├── cli.py              # CLI интерфейс (argparse)
├── config.py           # Загрузка YAML конфига
├── pipeline.py         # Оркестратор — запускает этапы по порядку
├── context.py          # PipelineContext — общее состояние между этапами
├── report.py           # Генерация отчётов
├── stages/
│   ├── __init__.py     # Базовый класс Stage + реестр @register
│   ├── commit.py       # Сбор git diff
│   ├── lint.py         # Запуск линтеров
│   ├── review.py       # AI код-ревью
│   ├── test.py         # Запуск тестов
│   ├── build.py        # Docker build
│   └── deploy.py       # Docker deploy
├── agent/
│   ├── client.py       # Ollama клиент + цикл вызова инструментов
│   ├── prompt.py       # Шаблоны промптов
│   └── tools.py        # Инструменты для AI-агентов
└── util/
    ├── proc.py         # Запуск процессов с таймаутом
    ├── git.py          # Git операции
    └── docker.py       # Docker операции
```
