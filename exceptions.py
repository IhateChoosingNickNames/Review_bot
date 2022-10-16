class YPBotException(Exception):
    """Кастомное исключение для обработки работы бота."""

    def __init__(self, func, message, error=None):
        """Инициализация атрибутов экземпляра."""
        self.func = func
        self.message = message
        self.error = error

    def __str__(self):
        """Строковое представление экземпляра ошибки."""
        if self.error:
            return f'{self.message} в функции {self.func} {self.error}'
        return f'{self.message} в функции {self.func}'


class NoUpdatesError(Exception):
    """Кастомное исключение обработки отсутствия обновлений."""

    pass
