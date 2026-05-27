from rest_framework import serializers
from apps.core.models import EmissionRecord, AuditLog


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_username = serializers.SerializerMethodField()
    batch_source = serializers.CharField(source='batch.source_type', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'scope_display', 'category', 'category_display',
            'activity_value', 'activity_unit', 'activity_unit_normalized',
            'co2e_kg', 'emission_factor_used',
            'period_start', 'period_end',
            'facility_name', 'location_country', 'employee_id',
            'vendor_name', 'description',
            'origin_iata', 'destination_iata', 'travel_class',
            'meter_id', 'tariff_code',
            'status', 'status_display', 'flag_reason',
            'reviewed_by_username', 'reviewed_at',
            'is_locked', 'source_amended',
            'batch_source', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'scope_display', 'category_display', 'status_display',
            'reviewed_by_username', 'batch_source', 'created_at', 'updated_at',
        ]

    def get_reviewed_by_username(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'username', 'old_value_json', 'new_value_json', 'timestamp', 'note']