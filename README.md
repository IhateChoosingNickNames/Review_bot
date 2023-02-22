# Review-status bot

Description: Simple bot for checking changes of status of sent work.
Getting response of Yandex.Practikum API.

Used technologies:
-
    - Python 3.7.9
    - python-dotenv 0.19.0
    - python-telegram-bot 13.7
    - requests 2.26.0
    - pytest 6.2.5
    - Simple JWT 4.7.2
    - Pytest 4.4.0
    - django-simple-captcha 0.5.17
Features:
-
    - Logging events.
    - Notifying about status changes
    - Checking for changes every 10 minutes

Installation:
-
    1. Clone the repository
    2. Install reqirements: pip install -r reqirements.txt
    3. Create .env-file and add keys: YP_TOKEN, BOT_TOKEN, CHAT_ID
    4. Run homework.py

Author: Larkin Michael