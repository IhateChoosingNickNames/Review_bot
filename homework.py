import http
import logging
import os
import sys
import time
from datetime import datetime
from logging import StreamHandler, getLogger
from typing import Dict, List, Optional, Type, Union

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import NotUpdatedError, YPBotException

load_dotenv()

PRACTICUM_TOKEN: Optional[str] = os.getenv("YP_TOKEN")
TELEGRAM_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID: Optional[str] = os.getenv("CHAT_ID")

RETRY_TIME: int = 600
ENDPOINT: str = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS: Dict[str, str] = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_STATUSES: Dict[str, str] = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


LOGGER_ANNOTATION = logging.Logger
SINGLE_HW_ANNOTATION = Dict[str, Union[str, float]]
HW_LIST_ANNOTATION = List[SINGLE_HW_ANNOTATION]
FROM_JSON_ANNOTATION = Dict[str, Union[HW_LIST_ANNOTATION, float]]
TIMESTAMP_ANNOTATION = Union[datetime, float]


def send_message(bot: Type[Bot], message: str) -> None:
    """Отправка сообщения от бота в чат пользователя."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info("Сообщение отправлено")
    except Exception as error:
        logger.error(error)


def get_api_answer(
    current_timestamp: TIMESTAMP_ANNOTATION
) -> FROM_JSON_ANNOTATION:
    """Получение ответа от АПИ и преобразование в JSON."""
    if isinstance(current_timestamp, datetime):
        current_timestamp = int(current_timestamp.timestamp())

    params: Dict[str, TIMESTAMP_ANNOTATION] = {"from_date": current_timestamp}
    response: requests.models.Response = requests.get(
        ENDPOINT, headers=HEADERS, params=params
    )

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


def check_response(response: FROM_JSON_ANNOTATION) -> HW_LIST_ANNOTATION:
    """Проверка наличия непустого списка по ключу homeworks."""
    try:
        response["homeworks"][0]
    except KeyError as error:
        raise YPBotException(
            check_response.__name__, "Ошибка получения записи", error
        )
    except IndexError:
        raise NotUpdatedError("Новых обновлений нет")
    else:
        return response["homeworks"]


def parse_status(homework: SINGLE_HW_ANNOTATION) -> str:
    """Формирование сообщения для отправки в чат."""
    homework_name: str = homework["homework_name"]

    homework_status: str = homework["status"]
    verdict: str = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверка наличия токенов и чат ID.

    Обязательные данные для запуска программы.
    """
    if not TELEGRAM_TOKEN or not PRACTICUM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    return True


def get_current_time() -> TIMESTAMP_ANNOTATION:
    """Создание точки отсчета для последующих запросов."""
    response: requests.models.Response = requests.get(
        ENDPOINT, headers=HEADERS, params={"from_date": 0}
    )
    try:
        response_json: FROM_JSON_ANNOTATION = response.json()
        last_homework: SINGLE_HW_ANNOTATION = response_json[
            "homeworks"
        ][0]
        date_: str = last_homework["date_updated"]
        if last_homework["status"] == "approved":
            return response_json["current_date"]
        return datetime.fromisoformat(date_[:-1])
    except Exception:
        return int(datetime.utcnow().timestamp())


def get_logger() -> logging.Logger:
    """Создание и настройка логгера."""
    logger: LOGGER_ANNOTATION = getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    # Для вывода в файл
    # handler: Type[logging] = RotatingFileHandler(
    #     "main.log", maxBytes=50000000, encoding="utf-8", backupCount=5
    # )
    handler: logging.StreamHandler = StreamHandler(
        stream=sys.stdout
    )
    logger.addHandler(hdlr=handler)
    formatter: logging.Formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    return logger


def main():
    """Основная логика работы программы."""
    if not check_tokens():
        logger.critical("Отсутствуют нужные параметры")
        raise YPBotException(main.__name__, "Отсутствуют нужные параметры")

    bot: Type[Bot.__class__] = Bot(token=TELEGRAM_TOKEN)
    message: Optional[str] = None
    error_message: Optional[str] = None

    while True:
        try:
            current_timestamp: Union[datetime, float] = get_current_time()
            response: FROM_JSON_ANNOTATION = get_api_answer(current_timestamp)
            checked_response: HW_LIST_ANNOTATION = check_response(response)
            new_message: str = parse_status(checked_response[0])
            if new_message != message:
                message = new_message
                send_message(bot, message)
            else:
                raise NotUpdatedError

        except NotUpdatedError as error:
            logger.debug(error)
            new_error_message: str = f"{error}"
            send_message(bot, new_error_message)

        except YPBotException as error:
            logger.error(error, exc_info=True)
            new_error_message: str = (
                f"Сбой в работе программы: {error.message}"
            )
            if new_error_message != error_message:
                error_message = new_error_message
                send_message(bot, new_error_message)

        except Exception as error:
            logger.critical(f"Непредвиденная ошибка {type(error).__name__}")
            new_error_message: str = f"Сбой в работе программы: {error}"
            if new_error_message != error_message:
                error_message = new_error_message
                send_message(bot, new_error_message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == "__main__":
    logger: LOGGER_ANNOTATION = get_logger()
    main()
