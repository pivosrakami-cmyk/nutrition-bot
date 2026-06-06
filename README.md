# Denis Nutrition Bot

## Установка на сервер

```bash
# 1. Клонируй репозиторий
git clone https://github.com/pivosrakami-cmyk/nutrition-bot.git
cd nutrition-bot

# 2. Установи зависимости
pip3 install -r requirements.txt

# 3. Запусти бота
python3 bot.py

# 4. Чтобы бот работал постоянно (systemd)
sudo nano /etc/systemd/system/nutrition-bot.service
```

## Systemd сервис
```ini
[Unit]
Description=Denis Nutrition Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/nutrition-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable nutrition-bot
sudo systemctl start nutrition-bot
```
