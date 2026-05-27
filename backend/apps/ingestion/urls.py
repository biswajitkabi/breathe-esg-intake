from django.urls import path
from .views import UploadView, BatchListView

urlpatterns = [
    path('upload/', UploadView.as_view(), name='upload'),
    path('batches/', BatchListView.as_view(), name='batches'),
]