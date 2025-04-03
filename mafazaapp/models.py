from decimal import ROUND_DOWN, Decimal
from math import exp
from django.utils.timezone import now
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django_countries.fields import CountryField  # Requires django-countries package
from django.core.exceptions import ValidationError
import json
from datetime import timedelta

# Status choices for user and transaction status
STATUS_CHOICES = (
    ('PENDING', 'Pending Approval'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
)

# Custom User Model
class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=15)
    address = models.TextField()
    country = CountryField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    has_requested = models.BooleanField(default=False)

    def __str__(self):
        return self.username

# Investment Project Model
class InvestmentProject(models.Model):
    project_name = models.CharField(max_length=255)
    total_investment = models.DecimalField(max_digits=15, decimal_places=2)
    min_roi = models.DecimalField(max_digits=5, decimal_places=2, help_text="Minimum Return on Investment (%)")
    max_roi = models.DecimalField(max_digits=5, decimal_places=2, help_text="Maximum Return on Investment (%)")
    project_description = models.TextField()
    image1 = models.ImageField(upload_to='project_images/', blank=True, null=True)
    image2 = models.ImageField(upload_to='project_images/', blank=True, null=True)
    image3 = models.ImageField(upload_to='project_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)  # Added active/inactive toggle
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.project_name


class AssignedProject(models.Model):
    RETURN_PERIOD_CHOICES = [
        ('2m', '2 Minute'),
        ('10m', '10 Minutes'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semiannual', 'Semiannual'),
        ('annual', 'Annual'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assigned_projects')
    project = models.ForeignKey(InvestmentProject, on_delete=models.CASCADE, related_name='assigned_users')
    rate_of_interest = models.DecimalField(max_digits=5, decimal_places=2, help_text="Rate of Interest (%)")
    return_period = models.CharField(max_length=20, choices=RETURN_PERIOD_CHOICES)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'project')
        
    def __str__(self):
        return f"{self.user.username} - {self.project.project_name} ({self.return_period})"
  
from django.utils import timezone
from django.contrib.auth.models import Group  
    
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('investment', 'Investment'),
        ('withdrawal', 'Withdrawal'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='transactions')
    project = models.ForeignKey(InvestmentProject, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    narration = models.TextField(blank=True, null=True)
    receipt = models.FileField(upload_to='transaction_receipts/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    # transaction_date = models.DateTimeField(auto_now_add=True)
    return_period = models.CharField(max_length=20, blank=True, null=True)  # From AssignedProject
    return_amount = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)  # Calculated return
    transaction_date = models.DateTimeField(default=timezone.now, editable=True) 
    
    
    def save(self, *args, **kwargs):
        # If the transaction is new and created by a regular user, set the date automatically
        if not self.pk and not self.user.groups.filter(name="Admin").exists():
            self.transaction_date = timezone.now()
        super().save(*args, **kwargs)
   
    @property
    def calculated_return(self):
        """
        Property to calculate the return amount without saving it to the database.
        """
        if self.status == "approved" and self.return_period == "2m":
            try:
                # Get the current time and calculate elapsed time in minutes
                current_time = now()
                elapsed_time = (current_time - self.transaction_date).total_seconds() / 60  # Time in minutes

                # Number of 2-minute periods
                period_minutes = Decimal("2")  # Use Decimal for 2-minute periods
                completed_periods = Decimal(elapsed_time) // period_minutes

                # Fetch rate of interest from the assigned project
                assigned_project = AssignedProject.objects.get(user=self.user, project=self.project)
                rate_as_decimal = Decimal(assigned_project.rate_of_interest) / Decimal("100")  # Convert to Decimal

                # Total minutes in a year as Decimal
                minutes_in_year = Decimal("525600")

                # Perform the calculation with consistent Decimal usage
                multiplier = Decimal(exp(float(rate_as_decimal * (completed_periods * period_minutes / minutes_in_year))))

                # Return the updated value rounded to 2 decimal places
                return round(Decimal(self.amount) * Decimal(multiplier - 1), 2)
            except AssignedProject.DoesNotExist:
                print("Assigned Project not found for this transaction.")
                return None
            except Exception as e:
                print(f"Error in calculated_return for Transaction ID {self.id}: {e}")
                return None
        return None

    def save_return_amount(self):
        """
        Method to calculate and save the return amount to the database.
        """
        if self.status == "approved" and self.return_period == "2m":
            current_time = now()
            # Check if 2 minutes have passed since the last calculation
            if self.last_calculated is None or (current_time - self.last_calculated).total_seconds() >= 120:
                return_amount = self.calculated_return
                if return_amount is not None:
                    self.return_amount = return_amount
                    self.last_calculated = current_time  # Update last calculation time
                    self.save()

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - {self.amount}"    
    
    
    
    from django.db import models



class UserLedger(models.Model):
    transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='ledger_entries')
    date = models.DateTimeField()
    project_name = models.CharField(max_length=255)
    narration = models.TextField(null=True, blank=True)
    principal_investment = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    returns = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    withdrawal = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    receipt = models.FileField(upload_to='transaction_receipts/', null=True, blank=True) 
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.date} - {self.project_name} - Balance: {self.balance}"
    
class PasswordResetRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('REJECTED', 'Rejected'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    processed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_resets')
    processed_at = models.DateTimeField(null=True, blank=True)
    temp_password = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-requested_at']
        
        
class UserDocument(models.Model):
    DOCUMENT_TYPES = (
        ('PASSPORT', 'Passport'),
        ('EMIRATES_ID', 'Emirates ID'),
        ('CONTRACT', 'Agreement/Contract'),
        ('PROOF_OF_ADDRESS', 'Proof of Address'),
        ('BANK_STATEMENT', 'Bank Statement'),
        ('SELFIE', 'Selfie with ID'),
        ('OTHER', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected - Needs Resubmission'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='user_documents/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reviewed_documents'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    expiration_date = models.DateField(blank=True, null=True)  # Useful for IDs/passports
    is_primary = models.BooleanField(default=False)  # For marking primary ID document

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'User Document'
        verbose_name_plural = 'User Documents'

    def __str__(self):
        return f"{self.user.username} - {self.get_document_type_display()} ({self.status})"

    def clean(self):
        # Validate that a user can only have one primary document of each type
        if self.is_primary:
            existing_primary = UserDocument.objects.filter(
                user=self.user,
                document_type=self.document_type,
                is_primary=True
            ).exclude(pk=self.pk).exists()
            
            if existing_primary:
                raise ValidationError(
                    f'User already has a primary {self.get_document_type_display()}'
                )

    def save(self, *args, **kwargs):
        # Automatically set passport or emirates ID as primary if no primary exists
        if not self.is_primary and self.document_type in ['PASSPORT', 'EMIRATES_ID']:
            has_primary = UserDocument.objects.filter(
                user=self.user,
                document_type=self.document_type,
                is_primary=True
            ).exists()
            
            if not has_primary:
                self.is_primary = True
                
        super().save(*args, **kwargs)     
        
from django.conf import settings  # Import settings
       
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class AdminNotification(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Use custom user model

    message = models.TextField()
    timestamp = models.DateTimeField(default=now)
    is_read = models.BooleanField(default=False)

    def mark_as_read(self):
        self.is_read = True
        self.save()

class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
