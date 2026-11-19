# Adrobot · справочник кампаний

Справочник кампаний с двумя режимами. Локальный режим хранит кампании и демонстрационные офферы в PostgreSQL. Режим Keitaro читает справочники и управляет кампаниями через Admin API. Статистика кликов в интерфейсе пока отсутствует.

Caddy проксирует запросы в FastAPI, который раздаёт API и интерфейс на AdminLTE с jQuery. SQLAlchemy подключается к PostgreSQL 17 через psycopg. Для работы с базой в браузере есть pgAdmin.

## Локальный запуск

Запустите Docker Engine или Docker Desktop с Linux-контейнерами. Из корня проекта выполните:

```sh
docker compose -f docker-compose.local.yml up --build --wait
docker compose -f docker-compose.local.yml ps
```

- [Стартовая страница](http://127.0.0.1:8000/) открывает справочник кампаний на AdminLTE.
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

При запуске контейнер FastAPI применяет миграции Alembic. Первичная миграция создаёт таблицы справочника и добавляет три демонстрационных оффера. Проверить установленную ревизию и соответствие схемы моделям:

```sh
docker compose -f docker-compose.local.yml exec app alembic current
docker compose -f docker-compose.local.yml exec app alembic check
```

Если приложение не запустилось из-за ошибки миграции, проверьте `docker compose -f docker-compose.local.yml logs app`. После исправления ошибки можно применить миграции через отдельный контейнер:

```sh
docker compose -f docker-compose.local.yml up -d --wait db
docker compose -f docker-compose.local.yml run --build --rm --no-deps app alembic upgrade head
docker compose -f docker-compose.local.yml up --build --wait
```

## Справочник

В справочнике можно создавать, открывать, редактировать и удалять кампании, а также добавлять и удалять офферы в каждой кампании. Доли в сумме дают 100%. В локальном режиме интерфейс показывает предполагаемую маршрутизацию.

## Режим Keitaro

В корневом файле `.env` задайте адрес трекера по HTTPS без `/admin` и API-ключ из профиля Keitaro. Этот файл исключён из Git.

```dotenv
KEITARO_URL=https://tracker.example.org
KEITARO_API_KEY=
KEITARO_CAMPAIGN_PREFIX=test_komarov_
KEITARO_ENABLE_ON_CREATE=false
```

Перезапустите Compose командой из раздела «Локальный запуск». Приложение покажет кампании с заданным префиксом, а в форме создания загрузит домены, группы, источники и офферы из трекера. Новая кампания получает геопоток с перенаправлением на Google и поток по умолчанию с выбранным оффером. По умолчанию кампания остаётся выключенной. Чтобы включать новые кампании после успешной настройки обоих потоков, задайте `KEITARO_ENABLE_ON_CREATE=true`. При ошибке на этапе создания потока кампания остаётся выключенной, а ответ содержит её ID.

Удаление кампании в этом режиме отправляет её в архив Keitaro. При изменении офферов доли активных офферов распределяются целыми процентами, а суммы округлений распределяются между первыми офферами.

Редактор поддерживает кампании с одним геопотоком на одну разрешённую страну и одним потоком офферов. Последний активный оффер защищён от удаления. Для проверки добавления и удаления на трекере нужны два доступных активных оффера. Для проверки маршрутизации включите тестовую кампанию и используйте её URL из вкладки **Tracking** в Keitaro. `/api/health` проверяет базу приложения. Доступ к Admin API можно проверить через `/api/settings` и `/api/offers`.
