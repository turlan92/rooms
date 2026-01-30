from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render, get_object_or_404
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import datetime
import requests
from .models import RefrigeratorData
from django.core.paginator import Paginator
import socket
import errno
from .models import Fridge
from .serializers import RefrigeratorDataSerializer
from django.http import JsonResponse


def fridge_list(request):
    fridges = Fridge.objects.all()
    return render(request, 'fr1/fridge_list.html', {'fridges': fridges})

def fridge_detail(request, fridge_id):
    fridge = get_object_or_404(Fridge, id=fridge_id)

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    start_date = parse_date(start_date_str) if start_date_str else None
    end_date = parse_date(end_date_str) if end_date_str else None

    filters = {}
    if start_date:
        filters['event_date__gte'] = datetime.combine(start_date, datetime.min.time())
    if end_date:
        filters['event_date__lte'] = datetime.combine(end_date, datetime.max.time())

    records_queryset = RefrigeratorData.objects.filter(fridge=fridge, **filters).order_by('-event_date')

    # --- Пагинация ---
    page_number = request.GET.get('page', 1)  # номер страницы из GET, по умолчанию 1
    paginator = Paginator(records_queryset, 100)  # 20 записей на страницу
    page_obj = paginator.get_page(page_number)  # безопасно получаем страницу

    return render(request, 'fr1/fridge_detail.html', {
        'fridge': fridge,
        'page_obj': page_obj,  # здесь теперь все записи текущей страницы
        'start_date_str': start_date_str,
        'end_date_str': end_date_str
    })

def daily_temperatures(request):
    # --- Даты из GET или сегодня по умолчанию ---
    start_date_str = request.GET.get('start_date', timezone.now().strftime('%Y-%m-%d'))
    end_date_str = request.GET.get('end_date', timezone.now().strftime('%Y-%m-%d'))

    try:
        start_date_obj = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
        end_date_obj = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
    except ValueError:
        start_date_obj = timezone.now()
        end_date_obj = timezone.now()

    # --- Queryset с фильтром по датам ---
    records_queryset = RefrigeratorData.objects.filter(
        event_date__range=(start_date_obj, end_date_obj)
    ).select_related('fridge').order_by('-event_date')

    # --- Пагинация ---
    page_number = request.GET.get('page', 1)
    paginator = Paginator(records_queryset, 20)  # 20 записей на страницу
    page_obj = paginator.get_page(page_number)

    # --- Если AJAX запрос, возвращаем JSON ---
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        records = []
        for rec in page_obj:
            records.append({
                'fridge_name': rec.fridge.name,
                'sensor1_temp': rec.sensor1_temp,
                'sensor2_temp': rec.sensor2_temp,
                'humidity': rec.humidity,
                'air_temp': rec.air_temp,
                'event_date': rec.event_date.strftime('%Y-%m-%d %H:%M'),
                'is_out_of_range': rec.is_out_of_range,
            })
        return JsonResponse({'records': records})

    # --- Обычный рендер шаблона ---
    return render(request, 'fr1/daily_temperatures.html', {
        'page_obj': page_obj,
        'start_date': start_date_str,
        'end_date': end_date_str,
    })

def emergencies(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    try:
        if start_date_str:
            start_date_obj = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
        else:
            start_date_obj = None

        if end_date_str:
            end_date_obj = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        else:
            end_date_obj = None
    except ValueError:
        start_date_obj = None
        end_date_obj = None

    # Фильтры для queryset
    filters = {}
    if start_date_obj:
        filters['event_date__gte'] = start_date_obj
    if end_date_obj:
        filters['event_date__lte'] = end_date_obj

    # Получаем queryset аварийных записей
    emergency_queryset = RefrigeratorData.objects.filter(is_out_of_range=True, **filters).select_related('fridge').order_by('-event_date')

    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(emergency_queryset, 20)  # 20 записей на страницу
    page_obj = paginator.get_page(page_number)

    # GET параметры для сохранения фильтров при переходе страниц
    get_params = ""
    if start_date_str:
        get_params += f"start_date={start_date_str}"
    if end_date_str:
        get_params += f"&end_date={end_date_str}" if get_params else f"end_date={end_date_str}"

    return render(request, 'fr1/emergencies.html', {
        'page_obj': page_obj,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'get_params': get_params
    })

TELEGRAM_BOT_TOKEN = "8031748926:AAGnjGN5qneH5w-aFg54SHCNRjBvQTJ0bXQ"
TELEGRAM_CHAT_ID = "-1003045548424"

@api_view(['POST'])
def create_refrigerator_data(request):
    """Принимает данные, сохраняет их и отправляет уведомление при аварийной температуре"""
    serializer = RefrigeratorDataSerializer(data=request.data)

    if serializer.is_valid():
        fridge = get_object_or_404(Fridge, id=request.data.get('fridge'))
        record = serializer.save(fridge=fridge)

        # Проверяем аварийную температуру
        if getattr(record, "is_out_of_range", False):
            message = (
                f"🚨 Аварийная температура в {fridge.name}!\n"
                f"🌡 Датчик 1: {record.sensor1_temp}°C\n"
                f"🌡 Датчик 2: {record.sensor2_temp}°C"
            )
            send_telegram_message(message)

        try:
            return Response({'message': 'Данные успешно сохранены!'}, status=status.HTTP_201_CREATED)
        except socket.error as e:
            if e.errno != errno.EPIPE:
                raise  # Пробрасываем, если это не Broken pipe

    try:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except socket.error as e:
        if e.errno != errno.EPIPE:
            raise

def send_telegram_message(message):
    """Отправляет сообщение в Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Ошибка: TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не установлены!")
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()  # Проверка ошибок HTTP
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка отправки в Telegram: {e}")
        return None

