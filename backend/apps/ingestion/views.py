import json
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from apps.core.models import (
    IngestionBatch, RawRecord, EmissionRecord, AuditLog, Tenant
)
from .serializers import UploadSerializer, IngestionBatchSerializer
from .parsers.sap_parser import parse_sap_csv
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser import parse_travel_json


def _get_or_create_demo_tenant():
    tenant, _ = Tenant.objects.get_or_create(
        slug='demo',
        defaults={'name': 'Demo Corp'}
    )
    return tenant


class UploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        source_type = serializer.validated_data['source_type']
        uploaded_file = serializer.validated_data['file']
        file_content = uploaded_file.read()

        tenant = _get_or_create_demo_tenant()

        # Create batch
        batch = IngestionBatch.objects.create(
            tenant=tenant,
            source_type=source_type,
            uploaded_by=request.user if request.user.is_authenticated else None,
            file_name=uploaded_file.name,
            status='PROCESSING',
        )

        # Parse
        try:
            if source_type == 'SAP':
                records, errors = parse_sap_csv(file_content)
            elif source_type == 'UTILITY':
                records, errors = parse_utility_csv(file_content)
            elif source_type == 'TRAVEL':
                records, errors = parse_travel_json(file_content)
            else:
                batch.status = 'FAILED'
                batch.save()
                return Response({'error': 'Unknown source type'}, status=400)
        except Exception as e:
            batch.status = 'FAILED'
            batch.notes = str(e)
            batch.save()
            return Response({'error': str(e)}, status=500)

        # Persist records
        created = 0
        for rec in records:
            raw_row = rec.pop('_raw_row', {})
            row_num = rec.pop('_row_num', 0)

            raw = RawRecord.objects.create(
                batch=batch,
                raw_json=raw_row,
                source_row_number=row_num,
            )

            emission = EmissionRecord.objects.create(
                tenant=tenant,
                batch=batch,
                raw_record=raw,
                scope=rec['scope'],
                category=rec['category'],
                activity_value=rec['activity_value'],
                activity_unit=rec['activity_unit'],
                activity_unit_normalized=rec['activity_unit_normalized'],
                co2e_kg=rec.get('co2e_kg'),
                emission_factor_used=rec.get('emission_factor_used', ''),
                period_start=rec['period_start'],
                period_end=rec['period_end'],
                facility_name=rec.get('facility_name', ''),
                location_country=rec.get('location_country', ''),
                employee_id=rec.get('employee_id', ''),
                vendor_name=rec.get('vendor_name', ''),
                description=rec.get('description', ''),
                origin_iata=rec.get('origin_iata', ''),
                destination_iata=rec.get('destination_iata', ''),
                travel_class=rec.get('travel_class', ''),
                meter_id=rec.get('meter_id', ''),
                tariff_code=rec.get('tariff_code', ''),
                status=rec.get('status', 'PENDING'),
                flag_reason=rec.get('flag_reason', ''),
            )

            AuditLog.objects.create(
                emission_record=emission,
                user=request.user if request.user.is_authenticated else None,
                action='CREATED',
                new_value_json={'source': source_type, 'row': row_num},
            )
            created += 1

        batch.row_count = created
        batch.error_count = len(errors)
        batch.status = 'DONE'
        batch.save()

        return Response({
            'batch_id': str(batch.id),
            'rows_created': created,
            'errors': errors,
            'status': 'DONE',
        }, status=status.HTTP_201_CREATED)


class BatchListView(APIView):
    def get(self, request):
        tenant = _get_or_create_demo_tenant()
        batches = IngestionBatch.objects.filter(tenant=tenant).order_by('-uploaded_at')
        serializer = IngestionBatchSerializer(batches, many=True)
        return Response(serializer.data)