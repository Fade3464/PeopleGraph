from django.urls import path

from .views import NameAddressLookupView, PhoneLookupView

app_name = 'lookups'

urlpatterns = [
    path('phone/', PhoneLookupView.as_view(), name='phone-lookup'),
    path('name-address/', NameAddressLookupView.as_view(), name='name-address-lookup'),
]
