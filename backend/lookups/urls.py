from django.urls import path

from .views import PhoneLookupView

app_name = 'lookups'

urlpatterns = [
    path('phone/', PhoneLookupView.as_view(), name='phone-lookup'),
]
