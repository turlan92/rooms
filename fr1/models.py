from django.db import models
from django.utils.timezone import now

class Fridge(models.Model):
    name = models.CharField(max_length=100)  # Название холодильника
    location = models.CharField(max_length=255, blank=True, null=True)  # Местоположение холодильника (опционально)
    image = models.ImageField(upload_to='fridges/', null=True, blank=True)  # Поле для изображения

    def __str__(self):
        return self.name

class RefrigeratorData(models.Model):
    fridge = models.ForeignKey(Fridge, on_delete=models.CASCADE, related_name='temperature_records')
    sensor1_temp = models.FloatField()
    sensor2_temp = models.FloatField()
    is_out_of_range = models.BooleanField()
    humidity = models.FloatField(null=True, blank=True)
    air_temp = models.FloatField(null=True, blank=True)
    event_date = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.fridge.name} ({self.event_date})"
