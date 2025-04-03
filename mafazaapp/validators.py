from decimal import Decimal
from django.core.exceptions import ValidationError
from django.conf import settings
import os

def validate_investment_amount(amount):
    """Validate investment amount is within allowed limits."""
    if amount < Decimal('1000.00'):
        raise ValidationError('Minimum investment amount is 1,000')
    if amount > Decimal('1000000000.00'):
        raise ValidationError('Maximum investment amount is 1,000,000,000')

def validate_withdrawal_amount(amount, available_balance):
    """Validate withdrawal amount against available balance."""
    if amount <= Decimal('0.00'):
        raise ValidationError('Withdrawal amount must be greater than 0')
    if amount > available_balance:
        raise ValidationError('Insufficient balance for withdrawal')
    if amount < Decimal('1000.00'):
        raise ValidationError('Minimum withdrawal amount is 1,000')

def validate_receipt_file(file):
    """Validate receipt file upload."""
    # Check file size (max 5MB)
    if file.size > 5 * 1024 * 1024:
        raise ValidationError('File size must not exceed 5MB')
    
    # Check file extension
    ext = os.path.splitext(file.name)[1].lower()
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
    if ext not in allowed_extensions:
        raise ValidationError('Invalid file type. Allowed types: JPG, JPEG, PNG, PDF')

def validate_transaction_rate_limit(user):
    """Validate transaction rate limit per user."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import Transaction
    
    # Check number of transactions in last 24 hours
    recent_transactions = Transaction.objects.filter(
        user=user,
        transaction_date__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    if recent_transactions >= 50:  # Max 50 transactions per 24 hours
        raise ValidationError('Transaction limit reached. Please try again later.')

def validate_project_status(project):
    """Validate project is active and available for transactions."""
    if not project.is_active:
        raise ValidationError('This project is currently inactive')
    
    # Add any additional project-specific validations here
    if hasattr(project, 'max_investors') and project.transactions.count() >= project.max_investors:
        raise ValidationError('Maximum number of investors reached for this project') 