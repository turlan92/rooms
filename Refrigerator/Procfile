release: python manage.py migrate
web: gunicorn lucid_mercy.wsgi --bind 0.0.0.0:$PORT
