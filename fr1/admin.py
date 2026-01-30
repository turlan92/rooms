from django.contrib import admin
from .models import Fridge, RefrigeratorData

class FridgeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'location', 'image')
    list_filter = ('location',)

class RefrigeratorDataAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'fridge',
        'event_date',
        'sensor1_temp',
        'sensor2_temp',
        'humidity',         # добавил
        'air_temp',         # добавил
        'is_out_of_range',
    )
    list_filter = ('fridge', 'is_out_of_range', 'event_date')  # добавил фильтры по новым булевым полям
    search_fields = ('fridge', 'event_date')

admin.site.register(Fridge, FridgeAdmin)
admin.site.register(RefrigeratorData, RefrigeratorDataAdmin)
