from django.contrib.postgres.fields import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from multiselectfield import MultiSelectField

from care.facility.models import CATEGORY_CHOICES, PatientBaseModel
from care.facility.models.mixins.permissions.patient import PatientRelatedPermissionMixin
from care.facility.models.patient_base import (
    ADMIT_CHOICES,
    REVERSE_SYMPTOM_CATEGORY_CHOICES,
    SYMPTOM_CHOICES,
    SuggestionChoices,
    reverse_choices,
)
from care.users.models import User
from care.facility.models.json_schema.consultation import LINES_CATHETERS
from care.utils.models.validators import JSONFieldSchemaValidator


class PatientConsultation(PatientBaseModel, PatientRelatedPermissionMixin):
    SUGGESTION_CHOICES = [
        (SuggestionChoices.HI, "HOME ISOLATION"),
        (SuggestionChoices.A, "ADMISSION"),
        (SuggestionChoices.R, "REFERRAL"),
        (SuggestionChoices.OP, "OP CONSULTATION"),
        (SuggestionChoices.DC, "DOMICILIARY CARE"),
    ]
    REVERSE_SUGGESTION_CHOICES = reverse_choices(SUGGESTION_CHOICES)

    patient = models.ForeignKey("PatientRegistration", on_delete=models.CASCADE, related_name="consultations")

    ip_no = models.CharField(max_length=100, default="", null=True, blank=True)

    facility = models.ForeignKey("Facility", on_delete=models.CASCADE, related_name="consultations")
    diagnosis = models.TextField(default="", null=True, blank=True)
    symptoms = MultiSelectField(choices=SYMPTOM_CHOICES, default=1, null=True, blank=True)
    other_symptoms = models.TextField(default="", blank=True)
    symptoms_onset_date = models.DateTimeField(null=True, blank=True)
    category = models.CharField(choices=CATEGORY_CHOICES, max_length=8, default=None, blank=True, null=True)
    examination_details = models.TextField(null=True, blank=True)
    existing_medication = models.TextField(null=True, blank=True)
    prescribed_medication = models.TextField(null=True, blank=True)
    consultation_notes = models.TextField(null=True, blank=True)
    course_in_facility = models.TextField(null=True, blank=True)
    discharge_advice = JSONField(default=dict)
    prescriptions = JSONField(default=dict)  # To be Used Later on
    suggestion = models.CharField(max_length=4, choices=SUGGESTION_CHOICES)
    referred_to = models.ForeignKey(
        "Facility", null=True, blank=True, on_delete=models.PROTECT, related_name="referred_patients",
    )
    admitted = models.BooleanField(default=False)
    admitted_to = models.IntegerField(choices=ADMIT_CHOICES, default=None, null=True, blank=True)
    admission_date = models.DateTimeField(null=True, blank=True)
    discharge_date = models.DateTimeField(null=True, blank=True)
    bed_number = models.CharField(max_length=100, null=True, blank=True)

    is_kasp = models.BooleanField(default=False)
    kasp_enabled_date = models.DateTimeField(null=True, blank=True, default=None)

    is_telemedicine = models.BooleanField(default=False)
    last_updated_by_telemedicine = models.BooleanField(default=False)

    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="patient_assigned_to")

    verified_by = models.TextField(default="", null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_user")

    last_edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="last_edited_user")

    # Physical Information

    height = models.FloatField(
        default=None, null=True, verbose_name="Patient's Height in CM", validators=[MinValueValidator(0)],
    )
    weight = models.FloatField(
        default=None, null=True, verbose_name="Patient's Weight in KG", validators=[MinValueValidator(0)],
    )

    # ICU Information

    cpk_mb = models.IntegerField(
        null=True,
        default=None,
        verbose_name="Patient's CPK/MB",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    operation = models.TextField(default=None, null=True)
    special_instruction = models.TextField(default=None, null=True)

    # Intubation details

    intubation_start_date = models.DateTimeField(null=True, blank=True, default=None)
    intubation_end_date = models.DateTimeField(null=True, blank=True, default=None)
    cuff_pressure = models.IntegerField(
        null=True, default=None, verbose_name="Cuff Pressure in mmhg", validators=[MinValueValidator(0)],
    )
    ett_tt = models.IntegerField(
        null=True,
        default=None,
        verbose_name="ETT/TT in mmid",
        validators=[MinValueValidator(3), MaxValueValidator(10)],
    )

    intubation_history = JSONField(default=list)

    # Lines and Catheters

    lines = JSONField(default=list, validators=[JSONFieldSchemaValidator(LINES_CATHETERS)])

    CSV_MAPPING = {
        "consultation_created_date": "Date of Consultation",
        "admission_date": "Date of Admission",
        "symptoms_onset_date": "Date of Onset of Symptoms",
        "symptoms": "Symptoms at time of consultation",
        "category": "Category",
        "examination_details": "Examination Details",
        "suggestion": "Suggestion",
    }

    CSV_MAKE_PRETTY = {
        "category": (lambda x: REVERSE_SYMPTOM_CATEGORY_CHOICES.get(x, "-")),
        "suggestion": (lambda x: PatientConsultation.REVERSE_SUGGESTION_CHOICES.get(x, "-")),
    }

    # CSV_DATATYPE_DEFAULT_MAPPING = {
    #     "admission_date": (None, models.DateTimeField(),),
    #     "symptoms_onset_date": (None, models.DateTimeField(),),
    #     "symptoms": ("-", models.CharField(),),
    #     "category": ("-", models.CharField(),),
    #     "examination_details": ("-", models.CharField(),),
    #     "suggestion": ("-", models.CharField(),),
    # }

    def __str__(self):
        return f"{self.patient.name}<>{self.facility.name}"

    def save(self, *args, **kwargs):
        """
        # Removing Patient Hospital Change on Referral
        if not self.pk or self.referred_to is not None:
            # pk is None when the consultation is created
            # referred to is not null when the person is being referred to a new facility
            self.patient.facility = self.referred_to or self.facility
            self.patient.save()
        """
        super(PatientConsultation, self).save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="if_referral_suggested",
                check=~models.Q(suggestion=SuggestionChoices.R) | models.Q(referred_to__isnull=False),
            ),
            models.CheckConstraint(
                name="if_admitted", check=models.Q(admitted=False) | models.Q(admission_date__isnull=False),
            ),
        ]
