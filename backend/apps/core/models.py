import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('ANALYST', 'Analyst'),
        ('VIEWER', 'Viewer'),
    ]
    tenant = models.ForeignKey(
        Tenant, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='users'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ANALYST')

    def __str__(self):
        return f"{self.username} ({self.tenant})"


class PlantLookup(models.Model):
    """Maps SAP WERKS plant codes to human-readable names."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='plant_lookups')
    werks_code = models.CharField(max_length=10)
    plant_name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('tenant', 'werks_code')

    def __str__(self):
        return f"{self.werks_code} → {self.plant_name}"


class IngestionBatch(models.Model):
    SOURCE_CHOICES = [
        ('SAP', 'SAP Fuel & Procurement'),
        ('UTILITY', 'Utility Electricity'),
        ('TRAVEL', 'Corporate Travel'),
    ]
    STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('DONE', 'Done'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    uploaded_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name='batches'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSING')
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.source_type} batch @ {self.uploaded_at:%Y-%m-%d %H:%M}"


class RawRecord(models.Model):
    """
    Immutable copy of exactly what came in.
    Never updated after creation — this is the source-of-truth.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='raw_records')
    raw_json = models.JSONField()          # original row, untouched
    source_row_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['source_row_number']

    def __str__(self):
        return f"RawRecord #{self.source_row_number} from {self.batch}"


class EmissionRecord(models.Model):
    """
    Normalized, reviewable emission row.
    One per activity event (one fuel purchase, one bill, one flight leg).
    """
    SCOPE_CHOICES = [
        (1, 'Scope 1 – Direct'),
        (2, 'Scope 2 – Electricity'),
        (3, 'Scope 3 – Value Chain'),
    ]
    CATEGORY_CHOICES = [
        ('FUEL', 'Fuel Combustion'),
        ('PROCUREMENT', 'Procurement'),
        ('ELECTRICITY', 'Electricity'),
        ('FLIGHT', 'Flight'),
        ('HOTEL', 'Hotel Stay'),
        ('GROUND', 'Ground Transport'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED', 'Flagged – Needs Attention'),
    ]
    UNIT_CHOICES = [
        ('L', 'Litres'),
        ('GAL', 'Gallons'),
        ('KG', 'Kilograms'),
        ('KWH', 'Kilowatt-hours'),
        ('MWH', 'Megawatt-hours'),
        ('KM', 'Kilometres'),
        ('MI', 'Miles'),
        ('NIGHTS', 'Nights'),
        ('OTHER', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='emission_records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='emission_records')
    raw_record = models.OneToOneField(
        RawRecord, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='emission_record'
    )

    # Classification
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    # Activity data — what was consumed/done
    activity_value = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    activity_unit_normalized = models.DecimalField(
        max_digits=18, decimal_places=4,
        help_text="Always in SI base unit (L, kWh, km)"
    )

    # Computed emissions
    co2e_kg = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True,
        help_text="kg CO2 equivalent — null if emission factor not available"
    )
    emission_factor_used = models.CharField(max_length=255, blank=True)

    # Time
    period_start = models.DateField()
    period_end = models.DateField()

    # Source context
    facility_name = models.CharField(max_length=255, blank=True)
    location_country = models.CharField(max_length=100, blank=True)
    employee_id = models.CharField(max_length=100, blank=True)
    vendor_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    # Travel-specific
    origin_iata = models.CharField(max_length=10, blank=True)
    destination_iata = models.CharField(max_length=10, blank=True)
    travel_class = models.CharField(max_length=50, blank=True)

    # Utility-specific
    meter_id = models.CharField(max_length=100, blank=True)
    tariff_code = models.CharField(max_length=100, blank=True)

    # Review workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    flag_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(
        default=False,
        help_text="True after audit export — no further edits allowed"
    )
    source_amended = models.BooleanField(
        default=False,
        help_text="True if this record was manually edited after ingestion"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'scope']),
            models.Index(fields=['batch']),
        ]

    def __str__(self):
        return f"{self.category} | {self.activity_value} {self.activity_unit} | {self.period_start}"


class AuditLog(models.Model):
    """Every change to an EmissionRecord is logged here."""
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED', 'Flagged'),
        ('EDITED', 'Edited'),
        ('LOCKED', 'Locked for Audit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emission_record = models.ForeignKey(
        EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs'
    )
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    old_value_json = models.JSONField(null=True, blank=True)
    new_value_json = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} on {self.emission_record_id} @ {self.timestamp}"