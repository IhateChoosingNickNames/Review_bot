import http
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NoUpdatesError, YPBotException

load_dotenv()

PRACTICUM_TOKEN = os.getenv("YP_TOKEN")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

RETRY_TIME = 5
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_STATUSES = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def send_message(bot, message):
    """Отправка сообщения от бота в чат пользователя."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info("Сообщение отправлено")
    except Exception as error:
        logger.error(error)


def get_api_answer(current_timestamp):
    """Получение ответа от АПИ и преобразование в JSON."""
    if isinstance(current_timestamp, datetime):
        current_timestamp = int(current_timestamp.timestamp())

    params = {"from_date": current_timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    if response.status_code != http.HTTPStatus.OK:
        raise YPBotException(
            get_api_answer.__name__, "Некорретный статус ответа"
        )

    try:
        return response.json()
    except Exception as error:
        raise YPBotException(
            get_api_answer.__name__, "Ошибка десериализации", error
        )


def check_response(response):
    """Проверка наличия непустого списка по ключу homeworks."""
    try:
        response["homeworks"][0]
    except KeyError as error:
        raise YPBotException(
            check_response.__name__, "Ошибка получения записи", error
        )
    except IndexError:
        raise NoUpdatesError("Новых обновлений нет")
    else:
        return response["homeworks"]


def parse_status(homework):
    """Формирование сообщения для отправки в чат."""
    homework_name = homework["homework_name"]

    homework_status = homework["status"]
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия токенов и чат ID.

    Обязательные данные для запуска программы.
    """
    if not TELEGRAM_TOKEN or not PRACTICUM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    return True


def get_current_time():
    """Создание точки отсчета для последующих запросов."""
    response = requests.get(ENDPOINT, headers=HEADERS, params={"from_date": 0})
    try:
        last_homework = response.json()["homeworks"][0]
        date_ = last_homework["date_updated"]
        if last_homework["status"] == "approved":
            return int(datetime.utcnow().timestamp())
        return datetime.fromisoformat(date_[:-1])
    except Exception:
        return int(datetime.utcnow().timestamp())


def get_logger():
    """Создание и настройка логгера."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        "main.log", maxBytes=50000000, encoding="utf-8", backupCount=5
    )
    logger.addHandler(handler)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    return logger


def main():
    """Основная логика работы программы."""
    if not check_tokens():
        logger.critical("Отсутствуют нужные параметры")
        raise YPBotException(main.__name__, "Отсутствуют нужные параметры")

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    message = None
    error_message = None

    while True:
        try:
            current_timestamp = get_current_time()
            response = get_api_answer(current_timestamp)
            checked_response = check_response(response)
            new_message = parse_status(checked_response[0])
            if new_message != message:
                message = new_message
                send_message(bot, message)
            else:
                raise NoUpdatesError

        except NoUpdatesError as error:
            logger.debug(error)
            new_error_message = f"{error}"
            send_message(bot, new_error_message)
        except YPBotException as error:
            logger.error(error, exc_info=True)
            new_error_message = f"Сбой в работе программы: {error.message}"
            if new_error_message != error_message:
                error_message = new_error_message
                send_message(bot, new_error_message)
        except Exception as error:
            logger.critical(f"Непредвиденная ошибка {type(error).__name__}")
            new_error_message = f"Сбой в работе программы: {error}"
            if new_error_message != error_message:
                error_message = new_error_message
                send_message(bot, new_error_message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == "__main__":
    logger = get_logger()
    main()
