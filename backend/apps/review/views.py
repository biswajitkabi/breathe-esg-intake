from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count, Q

from apps.core.models import EmissionRecord, AuditLog, Tenant
from .serializers import EmissionRecordSerializer, AuditLogSerializer


def _get_demo_tenant():
    tenant, _ = Tenant.objects.get_or_create(
        slug='demo', defaults={'name': 'Demo Corp'}
    )
    return tenant


class EmissionRecordListView(APIView):
    def get(self, request):
        tenant = _get_demo_tenant()
        qs = EmissionRecord.objects.filter(tenant=tenant).select_related(
            'batch', 'reviewed_by'
        )

        # Filters
        status_filter = request.query_params.get('status')
        scope_filter = request.query_params.get('scope')
        category_filter = request.query_params.get('category')
        source_filter = request.query_params.get('source_type')

        if status_filter:
            qs = qs.filter(status=status_filter)
        if scope_filter:
            qs = qs.filter(scope=scope_filter)
        if category_filter:
            qs = qs.filter(category=category_filter)
        if source_filter:
            qs = qs.filter(batch__source_type=source_filter)

        # Pagination handled by DRF settings (PAGE_SIZE=50)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = EmissionRecordSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = EmissionRecordSerializer(qs, many=True)
        return Response(serializer.data)

    def paginate_queryset(self, queryset):
        from rest_framework.pagination import PageNumberPagination
        self.paginator = PageNumberPagination()
        self.paginator.page_size = 50
        request = self.request
        return self.paginator.paginate_queryset(queryset, request)

    def get_paginated_response(self, data):
        return self.paginator.get_paginated_response(data)


class EmissionRecordDetailView(APIView):
    def get(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(EmissionRecordSerializer(record).data)

    def patch(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if record.is_locked:
            return Response({'error': 'Record is locked for audit'}, status=403)

        old_data = EmissionRecordSerializer(record).data
        serializer = EmissionRecordSerializer(record, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(source_amended=True)
            AuditLog.objects.create(
                emission_record=record,
                user=request.user if request.user.is_authenticated else None,
                action='EDITED',
                old_value_json=dict(old_data),
                new_value_json=request.data,
            )
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class ReviewActionView(APIView):
    """
    POST /api/review/records/<pk>/action/
    body: { "action": "APPROVE" | "REJECT" | "FLAG", "note": "..." }
    """
    def post(self, request, pk):
        try:
            record = EmissionRecord.objects.get(pk=pk)
        except EmissionRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if record.is_locked:
            return Response({'error': 'Record is locked for audit'}, status=403)

        action = request.data.get('action', '').upper()
        note = request.data.get('note', '')

        STATUS_MAP = {
            'APPROVE': 'APPROVED',
            'REJECT':  'REJECTED',
            'FLAG':    'FLAGGED',
        }

        if action not in STATUS_MAP:
            return Response({'error': f'Unknown action: {action}'}, status=400)

        old_status = record.status
        record.status = STATUS_MAP[action]
        record.reviewed_by = request.user if request.user.is_authenticated else None
        record.reviewed_at = timezone.now()
        if action == 'FLAG' and note:
            record.flag_reason = note
        record.save()

        AuditLog.objects.create(
            emission_record=record,
            user=request.user if request.user.is_authenticated else None,
            action=action if action != 'APPROVE' else 'APPROVED',
            old_value_json={'status': old_status},
            new_value_json={'status': record.status},
            note=note,
        )

        return Response({'status': record.status, 'record_id': str(pk)})


class BulkReviewActionView(APIView):
    """
    POST /api/review/records/bulk-action/
    body: { "ids": [...], "action": "APPROVE" | "REJECT" | "FLAG" }
    """
    def post(self, request):
        ids = request.data.get('ids', [])
        action = request.data.get('action', '').upper()
        note = request.data.get('note', '')

        STATUS_MAP = {
            'APPROVE': 'APPROVED',
            'REJECT':  'REJECTED',
            'FLAG':    'FLAGGED',
        }
        if action not in STATUS_MAP:
            return Response({'error': f'Unknown action: {action}'}, status=400)

        records = EmissionRecord.objects.filter(id__in=ids, is_locked=False)
        updated = 0
        for record in records:
            old_status = record.status
            record.status = STATUS_MAP[action]
            record.reviewed_by = request.user if request.user.is_authenticated else None
            record.reviewed_at = timezone.now()
            record.save()
            AuditLog.objects.create(
                emission_record=record,
                user=request.user if request.user.is_authenticated else None,
                action='APPROVED' if action == 'APPROVE' else action,
                old_value_json={'status': old_status},
                new_value_json={'status': record.status},
                note=note,
            )
            updated += 1

        return Response({'updated': updated})


class DashboardSummaryView(APIView):
    """Summary stats for the analyst dashboard header."""
    def get(self, request):
        tenant = _get_demo_tenant()
        qs = EmissionRecord.objects.filter(tenant=tenant)

        summary = {
            'total_records': qs.count(),
            'pending': qs.filter(status='PENDING').count(),
            'approved': qs.filter(status='APPROVED').count(),
            'flagged': qs.filter(status='FLAGGED').count(),
            'rejected': qs.filter(status='REJECTED').count(),
            'total_co2e_kg': qs.filter(
                status='APPROVED'
            ).aggregate(t=Sum('co2e_kg'))['t'] or 0,
            'by_scope': {
                'scope1': float(qs.filter(scope=1).aggregate(t=Sum('co2e_kg'))['t'] or 0),
                'scope2': float(qs.filter(scope=2).aggregate(t=Sum('co2e_kg'))['t'] or 0),
                'scope3': float(qs.filter(scope=3).aggregate(t=Sum('co2e_kg'))['t'] or 0),
            },
            'by_source': {
                src: qs.filter(batch__source_type=src).count()
                for src in ['SAP', 'UTILITY', 'TRAVEL']
            },
        }
        return Response(summary)


class AuditLogView(APIView):
    def get(self, request, pk):
        logs = AuditLog.objects.filter(emission_record_id=pk).select_related('user')
        return Response(AuditLogSerializer(logs, many=True).data)