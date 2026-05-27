from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Tenant, User, PlantLookup, IngestionBatch, EmissionRecord, AuditLog, RawRecord


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'tenant', 'role']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ESG', {'fields': ('tenant', 'role')}),
    )


@admin.register(PlantLookup)
class PlantLookupAdmin(admin.ModelAdmin):
    list_display = ['werks_code', 'plant_name', 'tenant', 'country']


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ['source_type', 'tenant', 'uploaded_at', 'status', 'row_count', 'error_count']
    list_filter = ['source_type', 'status']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['category', 'scope', 'activity_value', 'activity_unit', 'co2e_kg', 'status', 'period_start']
    list_filter = ['scope', 'category', 'status']
    search_fields = ['facility_name', 'vendor_name', 'meter_id']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['emission_record', 'user', 'action', 'timestamp']
    list_filter = ['action']