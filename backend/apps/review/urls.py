from django.urls import path
from .views import (
    EmissionRecordListView,
    EmissionRecordDetailView,
    ReviewActionView,
    BulkReviewActionView,
    DashboardSummaryView,
    AuditLogView,
)

urlpatterns = [
    path('records/', EmissionRecordListView.as_view(), name='records-list'),
    path('records/bulk-action/', BulkReviewActionView.as_view(), name='bulk-action'),
    path('records/<uuid:pk>/', EmissionRecordDetailView.as_view(), name='record-detail'),
    path('records/<uuid:pk>/action/', ReviewActionView.as_view(), name='record-action'),
    path('records/<uuid:pk>/audit/', AuditLogView.as_view(), name='record-audit'),
    path('summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
]