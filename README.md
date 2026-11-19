# Кампании Keitaro

Локальное окружение для сервиса управления кампаниями Keitaro. Caddy проксирует запросы в FastAPI, который раздаёт API и статический HTML с jQuery. SQLAlchemy подключается к PostgreSQL 17 через psycopg. Для работы с базой в браузере есть pgAdmin.

## Локальный запуск

Установите Docker с Compose и из корня проекта выполните:

```sh
docker compose -f docker-compose.local.yml up --build --wait
```

- [Стартовая страница](http://127.0.0.1:8000/) проверяет связь с API и базой.
- [Swagger UI](http://127.0.0.1:8000/docs) показывает доступные маршруты.
- [GET /api/health](http://127.0.0.1:8000/api/health) выполняет `SELECT 1` в PostgreSQL.
- [pgAdmin](http://127.0.0.1:5050/) открывается под `admin@keitaro.example.org` с паролем `localadmin`. Для преднастроенного сервера **Keitaro local** введите пароль базы `campaigns`.

Код FastAPI находится в `application/main.py`, HTML и JavaScript — в `application/static/`.

Порты Caddy и pgAdmin можно задать через `APP_PORT` и `PGADMIN_PORT` в файле `.env` в корне проекта. Изменения в папке `application/` подхватываются при разработке. После изменения `application/requirements.txt` перезапустите Compose с `--build`.

```sh
docker compose -f docker-compose.local.yml logs -f app
docker compose -f docker-compose.local.yml down
```

PostgreSQL и FastAPI доступны внутри сети Compose. Данные PostgreSQL и настройки pgAdmin хранятся в томах `postgres_data` и `pgadmin_data` и сохраняются после `down`. Конфиги сервисов находятся в `deploy/`.

Имя базы, пользователь и пароль для локальной разработки заданы в `deploy/postgresql/local/postgres.env`. Compose передаёт этот файл PostgreSQL и FastAPI. PostgreSQL использует эти значения при первом запуске с пустым томом. Чтобы сменить пользователя, пароль или имя базы в уже созданном томе, нужно отдельно изменить их в PostgreSQL.

## Миграции

На этапе локального каркаса база поднимается без таблиц приложения. Для проверки подключения миграции не требуются.
