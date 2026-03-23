# Convaier

Локальный AI-powered CI/CD конвейер для небольших команд разработки.

Convaier анализирует код, запускает линтеры, выполняет AI код-ревью, сканирует безопасность, считает метрики, прогоняет тесты и деплоит Docker-контейнеры.

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

Дополнительные зависимости (опциональные):

```bash
pip install -e ".[security]"   # bandit, pip-audit
pip install -e ".[metrics]"    # radon
pip install -e ".[rag]"        # chromadb
pip install -e ".[all]"        # всё сразу
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

# Посмотрите доступные языковые пресеты
convaier presets

# Запустите конвейер
convaier run
```

> Если команда `convaier` не найдена, используйте `python -m convaier` вместо неё.

## Команды CLI

| Команда | Описание |
|---------|----------|
| `convaier init` | Создать `convaier.yml` с примером конфигурации |
| `convaier check` | Проверить конфиг и подключение к Ollama |
| `convaier presets` | Показать доступные языковые пресеты |
| `convaier index` | Проиндексировать кодовую базу для RAG |
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
  language: python              # языковой пресет (python, javascript, typescript, java, go)

ollama:
  host: http://localhost:11434  # адрес Ollama
  model: qwen2.5-coder:3b      # модель для AI-анализа
  timeout: 300                  # таймаут LLM-запроса (секунды)
  num_ctx: 2048                 # размер контекстного окна (меньше = быстрее)

pipeline:
  fail_fast: true               # остановить при первой ошибке
  stages:                       # этапы конвейера (по порядку)
    - commit
    - security
    - review
    - metrics
    - test
    - build
    - deploy

stages:
  commit:
    diff_target: HEAD~1         # с чем сравнивать

  security:
    tools:                      # инструменты статического анализа
      - command: python -m bandit -r src/ -f json --quiet
        name: bandit
    ai_review: true             # AI-анализ безопасности поверх инструментов
    fail_on_critical: false     # провал при critical issues
    use_rag: false              # использовать RAG-контекст

  review:
    focus:                      # фокус AI-ревью
      - security
      - bugs
      - code quality
    max_files: 20               # максимум файлов для анализа
    max_diff_lines: 3000        # максимум строк diff
    use_rag: false              # использовать RAG-контекст

  metrics:
    src_path: src/              # путь к исходникам
    ai_review: false            # AI-рекомендации по метрикам

  test:
    command: python -m pytest tests/ --tb=short -q

  build:
    dockerfile: Dockerfile
    image_name: my-app
    tag: latest

  deploy:
    compose_file: docker-compose.yml
    service: app

reports:
  output_dir: .convaier/reports
  formats:
    - markdown
    - json
```

### Языковые пресеты

При указании `language` в конфиге автоматически подставляются настройки линтеров, security-инструментов и тестовых команд. Пользовательские настройки имеют приоритет над пресетом.

| Язык | Lint | Security | Test |
|------|------|----------|------|
| python | ruff, mypy | bandit | pytest |
| javascript | eslint | npm audit | jest |
| typescript | eslint, tsc | npm audit | jest |
| java | checkstyle | spotbugs | mvn test |
| go | golangci-lint | gosec | go test |

## Этапы конвейера

### commit

Собирает git diff и список изменённых файлов. Это основа для последующих этапов.

### security

Двухуровневый анализ безопасности:

1. **Инструменты** — запуск bandit, pip-audit и др. Парсит JSON-вывод, находит уязвимости с точными номерами строк и CWE.
2. **AI-анализ** — per-file анализ каждого изменённого файла через Ollama. Ищет уязвимости, которые статические инструменты могут пропустить. Получает результаты инструментов в контексте, чтобы не дублировать находки.

### review

AI код-ревью каждого изменённого файла через Ollama.

- Per-file анализ: каждый файл отправляется отдельным запросом (решает проблему таймаутов на больших проектах)
- Получает результаты security-этапа, чтобы не дублировать найденные уязвимости
- Может вызывать инструменты: `read_file`, `list_files`
- Возвращает комментарии с severity: `critical`, `warning`, `info`, `suggestion`

### metrics

Метрики качества кода через radon:

- **Cyclomatic complexity** — сложность функций (1-5 простая, 6-10 средняя, 11+ требует рефакторинга)
- **Maintainability index** — индекс поддерживаемости (0-9 низкий, 10-19 средний, 20+ хороший)
- **LOC** — количество строк кода
- Опциональные AI-рекомендации по улучшению

### test

Запускает тесты через указанную команду. Парсит вывод pytest для подсчёта passed/failed/skipped.

### build

Собирает Docker-образ. Пропускается автоматически, если предыдущие этапы упали.

### deploy

Запускает сервис через `docker compose up -d`. Пропускается, если build не прошёл.

## RAG (Retrieval Augmented Generation)

Convaier может индексировать кодовую базу и подставлять релевантный контекст в AI-запросы:

```bash
# Проиндексировать проект
convaier index

# Включить RAG в конфиге
stages:
  security:
    use_rag: true
  review:
    use_rag: true
```

Для RAG необходимы `chromadb` и модель эмбеддингов `nomic-embed-text`:

```bash
pip install -e ".[rag]"
ollama pull nomic-embed-text
```

## Отчёты

После каждого запуска генерируются отчёты в `.convaier/reports/`:

- **Markdown** (`run-YYYY-MM-DDTHH-MM-SS.md`) — человекочитаемый отчёт
- **JSON** (`run-YYYY-MM-DDTHH-MM-SS.json`) — машиночитаемые данные

## Архитектура

```
src/convaier/
├── cli.py              # CLI интерфейс (Rich)
├── config.py           # Загрузка YAML конфига + пресеты
├── pipeline.py         # Оркестратор — запускает этапы по порядку
├── context.py          # PipelineContext — общее состояние между этапами
├── report.py           # Генерация отчётов (Markdown + JSON)
├── presets.py          # Языковые пресеты (python, js, ts, java, go)
├── ui.py               # Rich console UI (панели, таблицы, иконки)
├── stages/
│   ├── __init__.py     # Базовый класс Stage + реестр @register
│   ├── commit.py       # Сбор git diff
│   ├── lint.py         # Запуск линтеров
│   ├── security.py     # Security анализ (инструменты + AI)
│   ├── review.py       # AI код-ревью (per-file)
│   ├── metrics.py      # Метрики кода (radon)
│   ├── test.py         # Запуск тестов
│   ├── build.py        # Docker build
│   └── deploy.py       # Docker deploy
├── agent/
│   ├── client.py       # Ollama клиент + agent loop
│   ├── prompt.py       # Шаблоны промптов
│   └── tools.py        # Инструменты для AI-агентов
├── rag/
│   ├── chunker.py      # Разбиение кода на чанки
│   ├── indexer.py       # Индексация в ChromaDB
│   └── search.py       # Поиск релевантного контекста
└── util/
    ├── proc.py         # Запуск процессов с таймаутом
    ├── git.py          # Git операции
    └── docker.py       # Docker операции
```
