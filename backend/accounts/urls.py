from django.urls import path

from .views import (
    csrf_token,
    export_lookup_results,
    feedback_list,
    login_view,
    logout_view,
    mark_feedback_read,
    me_view,
    phone_lookup_dashboard,
    submit_feedback,
)

app_name = 'accounts'

urlpatterns = [
    path('csrf/', csrf_token, name='csrf-token'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('me/', me_view, name='me'),
    path('dashboard/phone-lookups/', phone_lookup_dashboard, name='phone-lookup-dashboard'),
    path('exports/lookup-results/', export_lookup_results, name='export-lookup-results'),
    path('feedback/', submit_feedback, name='submit-feedback'),
    path('feedbacks/', feedback_list, name='feedback-list'),
    path('feedbacks/<int:feedback_id>/read/', mark_feedback_read, name='mark-feedback-read'),
]
