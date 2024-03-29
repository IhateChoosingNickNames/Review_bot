import http
import logging
import os
import sys
import time
from datetime import datetime
from logging import StreamHandler, getLogger
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Type, Union

import requests
from dotenv import load_dotenv
import telegram


from exceptions import NotUpdatedError, YPBotError

load_dotenv()

PRACTICUM_TOKEN: Optional[str] = os.getenv("YP_TOKEN")
TELEGRAM_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID: Optional[str] = os.getenv("CHAT_ID")

RETRY_PERIOD: int = 600
ENDPOINT: str = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS: Dict[str, str] = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS: Dict[str, str] = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


LOGGER_ANNOTATION = logging.Logger
SINGLE_HW_ANNOTATION = Dict[str, Union[str, int]]
HW_LIST_ANNOTATION = List[SINGLE_HW_ANNOTATION]
FROM_JSON_ANNOTATION = Dict[str, Union[HW_LIST_ANNOTATION, int]]
TIMESTAMP_ANNOTATION = Union[datetime, int]


def send_message(bot: Type[telegram.Bot], message: str) -> None:
    """Отправка сообщения от бота в чат пользователя."""
    try:
        logger.info("Попытка отправки сообщения")
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug("Сообщение отправлено")
    except Exception as error:
        logger.error("Сообщение отправлено")
        raise YPBotError(
            send_message.__name__, "Ошибка в работе Телеграма", error=error
        )


def get_api_answer(
    current_timestamp: TIMESTAMP_ANNOTATION,
) -> FROM_JSON_ANNOTATION:
    """Получение ответа от АПИ и преобразование в JSON."""
    if isinstance(current_timestamp, datetime):
        current_timestamp = int(current_timestamp.timestamp())

    params: Dict[str, TIMESTAMP_ANNOTATION] = {"from_date": current_timestamp}
    payload = {"url": ENDPOINT, "headers": HEADERS, "params": params}
    try:
        response: requests.models.Response = requests.get(**payload)
    except requests.exceptions.RequestException as error:
        raise YPBotError(
            get_api_answer.__name__, "Ошибка соединения с АПИ", error
        )

    if response.status_code != http.HTTPStatus.OK:
        raise YPBotError(get_api_answer.__name__, "Некорретный статус ответа")

    try:
        return response.json()
    except Exception as error:
        raise YPBotError(
            get_api_answer.__name__, "Ошибка десериализации", error
        )


def check_response(response: FROM_JSON_ANNOTATION) -> HW_LIST_ANNOTATION:
    """Проверка соответствия ответа от АПИ ожидаемым параметрам."""
    if not isinstance(response, dict):
        raise TypeError("Ответ приходит не в виде словаря")
    keys = ["homeworks", "current_date"]
    for key in keys:
        if key not in response:
            raise YPBotError(
                check_response.__name__, f"В ответе отсутствует ключ {key}"
            )
    if not isinstance(response["homeworks"], list):
        raise TypeError(
            check_response.__name__, "По ключу homeworks доступен не список"
        )
    return response["homeworks"]


def parse_status(homework: SINGLE_HW_ANNOTATION) -> str:
    """Формирование сообщения для отправки в чат."""
    if "homework_name" not in homework:
        raise KeyError("В ответе от АПИ отсутствует ключ homework_name")
    if "status" not in homework:
        raise KeyError("В ответе от АПИ отсутствует ключ status")
    homework_name: str = homework["homework_name"]
    homework_status: str = homework["status"]

    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError("В ответе от АПИ отсутствует ключ status")

    verdict: str = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверка наличия токенов и чат ID.

    Обязательные данные для запуска программы.
    """
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


# Пока функцию удалять не буду - надо узнать, корректно ли отработает без нее.
def get_current_time() -> TIMESTAMP_ANNOTATION:
    """Создание точки отсчета для последующих запросов."""
    payload = {"url": ENDPOINT, "headers": HEADERS, "params": {"from_date": 0}}
    response: requests.models.Response = requests.get(**payload)
    try:
        response_json: FROM_JSON_ANNOTATION = response.json()
        last_homework: SINGLE_HW_ANNOTATION = response_json["homeworks"][0]
        if last_homework["status"] == "approved":
            return response_json["current_date"]
        date_: str = last_homework["date_updated"]
        return datetime.fromisoformat(date_[:-1])
    except Exception:
        return int(datetime.utcnow().timestamp())


def get_logger() -> logging.Logger:
    """Создание и настройка логгера."""
    logger: LOGGER_ANNOTATION = getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    # Для вывода в файл
    # handler: logging.StreamHandler = RotatingFileHandler(
    #     __file__ + '.log', maxBytes=50000000, encoding="utf-8", backupCount=5
    # )
    handler: logging.StreamHandler = StreamHandler(stream=sys.stdout)
    logger.addHandler(hdlr=handler)
    formatter: logging.Formatter = logging.Formatter(
        (
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s "
            "- %(lineno)d - %(message)s"
        )
    )
    handler.setFormatter(formatter)
    return logger


def main():
    """Основная логика работы программы."""
    logger.info("Начало логгирования")
    if not check_tokens():
        logger.critical("Отсутствуют нужные параметры")
        sys.exit("Отсутствуют нужные параметры")

    bot: Type[telegram.Bot.__class__] = telegram.Bot(token=TELEGRAM_TOKEN)
    message: Optional[str] = None
    error_message: Optional[str] = None
    new_error_message: Optional[str] = None
    new_message: Optional[str] = None
    current_timestamp = get_current_time()

    while True:
        try:
            # Добавить в саму функцию логгер нельзя - тесты не видят логгер
            logger.info("Попытка получения ответа от АПИ")
            response: FROM_JSON_ANNOTATION = get_api_answer(current_timestamp)
            logger.info("Ответ от АПИ получен")
            current_timestamp: int = response.get(
                "current_date", current_timestamp
            )

            checked_response: HW_LIST_ANNOTATION = check_response(response)
            if checked_response:
                new_message: str = parse_status(checked_response[0])
            if new_message != message:
                message = new_message
                send_message(bot, message)
            else:
                raise NotUpdatedError("Нет обновлений")

        except NotUpdatedError as error:
            logger.debug(error)

        except YPBotError as error:
            logger.error(error, exc_info=True)
            new_error_message: str = (
                f"Сбой в работе программы: {error.message}"
            )

        except Exception as error:
            logger.critical(
                f"Непредвиденная ошибка {type(error).__name__} {error}",
                exc_info=True,
            )
            new_error_message: str = f"Сбой в работе программы: {error}"

        finally:
            if new_error_message and new_error_message != error_message:
                error_message = new_error_message
                try:
                    send_message(bot, new_error_message)
                except YPBotError as error:
                    logger.error(error, exc_info=True)

            time.sleep(RETRY_PERIOD)

logger: LOGGER_ANNOTATION = get_logger()
if __name__ == "__main__":

    main()
