from rest_framework import serializers
from apps.core.models import IngestionBatch, EmissionRecord, RawRecord


class IngestionBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'source_type', 'uploaded_at', 'file_name',
            'status', 'row_count', 'error_count', 'notes'
        ]
        read_only_fields = fields


class UploadSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=['SAP', 'UTILITY', 'TRAVEL'])
    file = serializers.FileField()