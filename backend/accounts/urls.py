from django.urls import path

from .views import csrf_token, login_view, logout_view, me_view, phone_lookup_dashboard

app_name = 'accounts'

urlpatterns = [
    path('csrf/', csrf_token, name='csrf-token'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('me/', me_view, name='me'),
    path('dashboard/phone-lookups/', phone_lookup_dashboard, name='phone-lookup-dashboard'),
]
