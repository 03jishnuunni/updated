from .models import AssignedProject, Transaction, UserLedger, CustomUser
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Sum

from django.utils import timezone
from datetime import timedelta




from django.core.exceptions import ValidationError
from django.utils.timezone import now
from decimal import Decimal
from datetime import timedelta

def create_transaction(user, project, amount, transaction_type, receipt, narration):
    print(f"Transaction Debug - Type: {transaction_type}, Amount: {amount}, Project: {project.project_name}")

    # Get LAST ledger entry FOR THIS SPECIFIC PROJECT
    last_ledger = UserLedger.objects.filter(
        transaction__user=user,
        project_name=project.project_name
    ).order_by('-date').first()
    
    current_balance = last_ledger.balance if last_ledger else Decimal('0.00')
    print(f"DEBUG: Current balance for project {project.project_name}: {current_balance}")

    # Withdrawal logic
    if transaction_type == 'withdrawal':
        print("\nDEBUG: Processing WITHDRAWAL")
        
        if not last_ledger or current_balance < amount:
            error_msg = f"Insufficient balance in project {project.project_name} for withdrawal. Current balance: {current_balance}"
            print(f"DEBUG: {error_msg}")
            raise ValidationError(error_msg)

        new_balance = current_balance - amount
        print(f"DEBUG: New balance will be: {new_balance}")

        transaction = Transaction.objects.create(
            user=user,
            project=project,
            amount=amount,
            transaction_type='withdrawal',
            receipt=receipt,  
            narration=narration,
        )

        UserLedger.objects.create(
            transaction=transaction,
            date=now(),
            project_name=project.project_name,
            principal_investment=Decimal('0.00'),
            returns=Decimal('0.00'),
            withdrawal=amount,
            balance=new_balance,
            receipt=receipt,
            narration=narration
        )

        print(f"Withdrawal processed. New Balance for {project.project_name}: {new_balance}")
        return transaction

    # Investment logic
    elif transaction_type == 'investment':
        print("\nDEBUG: Processing INVESTMENT")
        
        assigned_project = AssignedProject.objects.get(
            user=user,
            project=project
        )
        roi = assigned_project.rate_of_interest / Decimal('100')
        annual_return = amount * roi
        interval_return = (annual_return / Decimal('525600')) * Decimal('2')

        new_balance = current_balance + interval_return
        
        print(f"DEBUG: Project ROI: {assigned_project.rate_of_interest}%")
        print(f"DEBUG: 2-minute return: {interval_return}")
        print(f"DEBUG: New balance will be: {new_balance}")

        transaction = Transaction.objects.create(
            user=user,
            project=project,
            amount=amount,
            transaction_type='investment',
            status='pending',
            receipt=receipt,
            narration=narration,
        )

        UserLedger.objects.create(
            transaction=transaction,
            date=now(),
            project_name=project.project_name,
            principal_investment=amount,
            returns=interval_return,
            withdrawal=Decimal('0.00'),
            balance=new_balance,
            receipt=receipt,
            narration=narration
        )

        print(f"Investment processed. New Balance for {project.project_name}: {new_balance}")
        return transaction

def update_user_ledger(transaction):
    # Get the last balance from the ledger FOR THIS SPECIFIC PROJECT
    last_ledger = UserLedger.objects.filter(
        transaction__user=transaction.user,
        project_name=transaction.project.project_name
    ).order_by('-date').first()
    
    last_balance = last_ledger.balance if last_ledger else Decimal('0.00')
    print(f"DEBUG: Updating ledger for project {transaction.project.project_name}. Last balance: {last_balance}")

    if transaction.transaction_type == 'investment':
        try:
            assigned_project = AssignedProject.objects.get(
                user=transaction.user,
                project=transaction.project
            )
            roi = assigned_project.rate_of_interest / Decimal('100')
            annual_return = transaction.amount * roi
            interval_return = (annual_return / Decimal('525600')) * Decimal('2')

            new_balance = last_balance + interval_return
            print(f"DEBUG: Adding {interval_return} to project {transaction.project.project_name}. New balance: {new_balance}")

            UserLedger.objects.create(
                transaction=transaction,
                date=now(),
                project_name=transaction.project.project_name,
                principal_investment=transaction.amount,
                returns=interval_return,
                withdrawal=Decimal('0.00'),
                balance=new_balance,
            )

        except AssignedProject.DoesNotExist:
            raise ValidationError(f"No project assignment found for {transaction.user} in {transaction.project}")

    elif transaction.transaction_type == 'withdrawal':
        if last_balance < transaction.amount:
            raise ValidationError(
                f"Insufficient balance in project {transaction.project.project_name}. "
                f"Available: {last_balance}, Attempted withdrawal: {transaction.amount}"
            )
        
        new_balance = last_balance - transaction.amount
        print(f"DEBUG: Deducting {transaction.amount} from project {transaction.project.project_name}. New balance: {new_balance}")

        UserLedger.objects.create(
            transaction=transaction,
            date=now(),
            project_name=transaction.project.project_name,
            principal_investment=Decimal('0.00'),
            returns=Decimal('0.00'),
            withdrawal=transaction.amount,
            balance=new_balance,
        )


def generate_missed_returns():
    transactions = Transaction.objects.filter(transaction_type='investment', status='approved')

    for transaction in transactions:
        try:
            assigned_project = AssignedProject.objects.get(
                user=transaction.user,
                project=transaction.project
            )
        except AssignedProject.DoesNotExist:
            continue

        if assigned_project.return_period != '2m':
            continue

        last_ledger = UserLedger.objects.filter(
            transaction__user=transaction.user,
            project_name=transaction.project.project_name
        ).order_by('-date').first()
        
        current_time = now()

        # ✅ Find the last return entry (ignore withdrawals)
        last_return_entry = UserLedger.objects.filter(
            transaction__user=transaction.user,
            project_name=transaction.project.project_name,
            returns__gt=Decimal('0.00')  # Only consider return entries
        ).order_by('-date').first()

        if last_return_entry:
            correct_next_time = (last_return_entry.date + timedelta(minutes=2)).replace(second=0)
        else:
            correct_next_time = (last_ledger.date + timedelta(minutes=2)).replace(second=0)

        while correct_next_time <= current_time:
            roi = assigned_project.rate_of_interest / Decimal('100')
            annual_return = transaction.amount * roi
            interval_return = (annual_return / Decimal('525600')) * Decimal('2')

            last_balance = UserLedger.objects.filter(
                transaction__user=transaction.user,
                project_name=transaction.project.project_name
            ).order_by('-date').first().balance

            new_balance = last_balance + interval_return

            last_ledger = UserLedger.objects.create(
                transaction=transaction,
                date=correct_next_time,  # ✅ Ensures correct timing even after withdrawal
                project_name=transaction.project.project_name,
                principal_investment=Decimal('0.00'),
                returns=interval_return,
                withdrawal=Decimal('0.00'),
                balance=new_balance,
                receipt=transaction.receipt
            )
            print(f"DEBUG: Added return at {correct_next_time} for {transaction.project.project_name}. New balance: {new_balance}")

            correct_next_time += timedelta(minutes=2) 





# firstone
# firstone
# firstone
# firstone
# firstone
# firstone

def update_user_ledger(transaction):
    # Get the last balance from the ledger FOR THIS SPECIFIC PROJECT
    last_ledger = UserLedger.objects.filter(
        transaction__user=transaction.user,
        project_name=transaction.project.project_name
    ).order_by('-date').first()
    
    last_balance = last_ledger.balance if last_ledger else Decimal('0.00')
    print(f"DEBUG: Updating ledger for project {transaction.project.project_name}. Last balance: {last_balance}")

    if transaction.transaction_type == 'investment':
        try:
            assigned_project = AssignedProject.objects.get(
                user=transaction.user,
                project=transaction.project
            )
            roi = assigned_project.rate_of_interest / Decimal('100')
            annual_return = transaction.amount * roi
            interval_return = (annual_return / Decimal('525600')) * Decimal('2')

            new_balance = last_balance + interval_return
            print(f"DEBUG: Adding {interval_return} to project {transaction.project.project_name}. New balance: {new_balance}")

            UserLedger.objects.create(
                transaction=transaction,
                date=now(),
                project_name=transaction.project.project_name,
                principal_investment=transaction.amount,
                returns=interval_return,
                withdrawal=Decimal('0.00'),
                balance=new_balance,
            )

        except AssignedProject.DoesNotExist:
            raise ValidationError(f"No project assignment found for {transaction.user} in {transaction.project}")

    elif transaction.transaction_type == 'withdrawal':
        if last_balance < transaction.amount:
            raise ValidationError(
                f"Insufficient balance in project {transaction.project.project_name}. "
                f"Available: {last_balance}, Attempted withdrawal: {transaction.amount}"
            )
        
        new_balance = last_balance - transaction.amount
        print(f"DEBUG: Deducting {transaction.amount} from project {transaction.project.project_name}. New balance: {new_balance}")

        UserLedger.objects.create(
            transaction=transaction,
            date=now(),
            project_name=transaction.project.project_name,
            principal_investment=Decimal('0.00'),
            returns=Decimal('0.00'),
            withdrawal=transaction.amount,
            balance=new_balance,
        )
        
        
from dateutil.relativedelta import relativedelta       
def create_transaction(user, project, amount, transaction_type, receipt, narration):
    print(f"Transaction Debug - Type: {transaction_type}, Amount: {amount}, Project: {project.project_name}")

    # Get LAST ledger entry FOR THIS SPECIFIC PROJECT
    last_ledger = UserLedger.objects.filter(
        transaction__user=user,
        project_name=project.project_name
    ).order_by('-date').first()
    
    current_balance = last_ledger.balance if last_ledger else Decimal('0.00')
    print(f"DEBUG: Current balance for project {project.project_name}: {current_balance}")

    # Withdrawal logic
    if transaction_type == 'withdrawal':
        print("\nDEBUG: Processing WITHDRAWAL")
        
        if not last_ledger or current_balance < amount:
            error_msg = f"Insufficient balance in project {project.project_name} for withdrawal. Current balance: {current_balance}"
            print(f"DEBUG: {error_msg}")
            raise ValidationError(error_msg)

        new_balance = current_balance - amount
        print(f"DEBUG: New balance will be: {new_balance}")

        transaction = Transaction.objects.create(
            user=user,
            project=project,
            amount=amount,
            transaction_type='withdrawal',
            receipt=receipt,  
            narration=narration,
        )

        UserLedger.objects.create(
            transaction=transaction,
            date=now(),
            project_name=project.project_name,
            principal_investment=Decimal('0.00'),
            returns=Decimal('0.00'),
            withdrawal=amount,
            balance=new_balance,
            receipt=receipt,
            narration=narration
        )

        print(f"Withdrawal processed. New Balance for {project.project_name}: {new_balance}")
        return transaction

    # Investment logic
    elif transaction_type == 'investment':
        print("\nDEBUG: Processing INVESTMENT")
        
        assigned_project = AssignedProject.objects.get(
            user=user,
            project=project
        )
        roi = assigned_project.rate_of_interest / Decimal('100')
        annual_return = amount * roi
        
        # Calculate interval return based on return period
        if assigned_project.return_period == '2m':
            interval_return = (annual_return / Decimal('525600')) * Decimal('2')  # 2 minutes
        elif assigned_project.return_period == '10m':
            interval_return = (annual_return / Decimal('52560')) * Decimal('10')  # 10 minutes
        elif assigned_project.return_period == 'monthly':
            interval_return = annual_return / Decimal('12')  # Monthly
        elif assigned_project.return_period == 'quarterly':
            interval_return = annual_return / Decimal('4')  # Quarterly
        elif assigned_project.return_period == 'semiannual':
            interval_return = annual_return / Decimal('2')  # Semiannual
        elif assigned_project.return_period == 'annual':
            interval_return = annual_return  # Annual
        else:
            interval_return = Decimal('0.00')

        new_balance = current_balance + interval_return
        
        print(f"DEBUG: Project ROI: {assigned_project.rate_of_interest}%")
        print(f"DEBUG: {assigned_project.return_period} return: {interval_return}")
        print(f"DEBUG: New balance will be: {new_balance}")

        transaction = Transaction.objects.create(
            user=user,
            project=project,
            amount=amount,
            transaction_type='investment',
            status='pending',
            receipt=receipt,
            narration=narration,
        )

        UserLedger.objects.create(
            transaction=transaction,
            date=now(),
            project_name=project.project_name,
            principal_investment=amount,
            returns=interval_return,
            withdrawal=Decimal('0.00'),
            balance=new_balance,
            receipt=receipt,
            narration=narration
        )

        print(f"Investment processed. New Balance for {project.project_name}: {new_balance}")
        return transaction

def generate_missed_returns():
    transactions = Transaction.objects.filter(transaction_type='investment', status='approved')

    for transaction in transactions:
        try:
            assigned_project = AssignedProject.objects.get(
                user=transaction.user,
                project=transaction.project
            )
        except AssignedProject.DoesNotExist:
            continue

        last_ledger = UserLedger.objects.filter(
            transaction__user=transaction.user,
            project_name=transaction.project.project_name
        ).order_by('-date').first()
        
        current_time = now()

        # Find the last return entry (ignore withdrawals)
        last_return_entry = UserLedger.objects.filter(
            transaction__user=transaction.user,
            project_name=transaction.project.project_name,
            returns__gt=Decimal('0.00')  # Only consider return entries
        ).order_by('-date').first()

        if last_return_entry:
            if assigned_project.return_period == '2m':
                correct_next_time = (last_return_entry.date + timedelta(minutes=2)).replace(second=0)
            elif assigned_project.return_period == '10m':
                correct_next_time = (last_return_entry.date + timedelta(minutes=10)).replace(second=0)
            elif assigned_project.return_period == 'monthly':
                correct_next_time = (last_return_entry.date + relativedelta(months=1)).replace(day=1)
            elif assigned_project.return_period == 'quarterly':
                correct_next_time = (last_return_entry.date + relativedelta(months=3)).replace(day=1)
            elif assigned_project.return_period == 'semiannual':
                correct_next_time = (last_return_entry.date + relativedelta(months=6)).replace(day=1)
            elif assigned_project.return_period == 'annual':
                correct_next_time = (last_return_entry.date + relativedelta(years=1)).replace(month=1, day=1)
        else:
            if assigned_project.return_period == '2m':
                correct_next_time = (last_ledger.date + timedelta(minutes=2)).replace(second=0)
            elif assigned_project.return_period == '10m':
                correct_next_time = (last_ledger.date + timedelta(minutes=10)).replace(second=0)
            elif assigned_project.return_period == 'monthly':
                correct_next_time = (last_ledger.date + relativedelta(months=1)).replace(day=1)
            elif assigned_project.return_period == 'quarterly':
                correct_next_time = (last_ledger.date + relativedelta(months=3)).replace(day=1)
            elif assigned_project.return_period == 'semiannual':
                correct_next_time = (last_ledger.date + relativedelta(months=6)).replace(day=1)
            elif assigned_project.return_period == 'annual':
                correct_next_time = (last_ledger.date + relativedelta(years=1)).replace(month=1, day=1)

        while correct_next_time <= current_time:
            roi = assigned_project.rate_of_interest / Decimal('100')
            annual_return = transaction.amount * roi
            
            # Calculate interval return based on return period
            if assigned_project.return_period == '2m':
                interval_return = (annual_return / Decimal('525600')) * Decimal('2')
            elif assigned_project.return_period == '10m':
                interval_return = (annual_return / Decimal('52560')) * Decimal('10')
            elif assigned_project.return_period == 'monthly':
                interval_return = annual_return / Decimal('12')
            elif assigned_project.return_period == 'quarterly':
                interval_return = annual_return / Decimal('4')
            elif assigned_project.return_period == 'semiannual':
                interval_return = annual_return / Decimal('2')
            elif assigned_project.return_period == 'annual':
                interval_return = annual_return
            else:
                interval_return = Decimal('0.00')

            last_balance = UserLedger.objects.filter(
                transaction__user=transaction.user,
                project_name=transaction.project.project_name
            ).order_by('-date').first().balance

            new_balance = last_balance + interval_return

            last_ledger = UserLedger.objects.create(
                transaction=transaction,
                date=correct_next_time,
                project_name=transaction.project.project_name,
                principal_investment=Decimal('0.00'),
                returns=interval_return,
                withdrawal=Decimal('0.00'),
                balance=new_balance,
                receipt=transaction.receipt
            )
            print(f"DEBUG: Added return at {correct_next_time} for {transaction.project.project_name}. New balance: {new_balance}")

            # Calculate next return time based on return period
            if assigned_project.return_period == '2m':
                correct_next_time += timedelta(minutes=2)
            elif assigned_project.return_period == '10m':
                correct_next_time += timedelta(minutes=10)
            elif assigned_project.return_period == 'monthly':
                correct_next_time += relativedelta(months=1)
            elif assigned_project.return_period == 'quarterly':
                correct_next_time += relativedelta(months=3)
            elif assigned_project.return_period == 'semiannual':
                correct_next_time += relativedelta(months=6)
            elif assigned_project.return_period == 'annual':
                correct_next_time += relativedelta(years=1)        



# sorteddd
# divmoddd
# ddd
# divmodd
# divmodd

# from decimal import Decimal
# from datetime import timedelta
# from django.utils.timezone import now
# from dateutil.relativedelta import relativedelta
# from django.core.exceptions import ValidationError
# from .models import UserLedger, Transaction, AssignedProject



# def create_transaction(user, project, amount, transaction_type, receipt=None):
#     """Create a new transaction and update the ledger"""
#     try:
#         # Create the transaction
#         transaction = Transaction.objects.create(
#             user=user,
#             project=project,
#             amount=amount,
#             transaction_type=transaction_type,
#             receipt=receipt,
#             status='pending'
#         )
        
#         # Get the latest ledger entry for this project
#         last_ledger = UserLedger.objects.filter(
#             transaction__user=user,
#             project_name=project.project_name
#         ).order_by('-date').first()
        
#         # Calculate the new balance
#         if last_ledger:
#             current_balance = last_ledger.balance
#         else:
#             current_balance = Decimal('0.00')
            
#         # Update balance based on transaction type
#         if transaction_type == 'investment':
#             # Get assigned project details for rate calculation
#             assigned_project = AssignedProject.objects.get(
#                 user=user,
#                 project=project
#             )
            
#             # Calculate return based on investment amount and assigned rate
#             rate = assigned_project.rate_of_interest
#             periodic_rate = (rate / Decimal('100.0')) * (Decimal('2') / (Decimal('365.0') * Decimal('24.0') * Decimal('60.0')))
#             return_amount = amount * periodic_rate
#             return_amount = return_amount.quantize(Decimal('0.01'))
            
#             # Create new ledger entry
#             ledger_entry = UserLedger.objects.create(
#                 transaction=transaction,
#                 project_name=project.project_name,
#                 principal_investment=amount,
#                 returns=return_amount,
#                 withdrawal=Decimal('0.00'),
#                 balance=current_balance + return_amount,
#                 date=timezone.now()
#             )
            
#         elif transaction_type == 'withdrawal':
#             if current_balance < amount:
#                 raise ValidationError(f"Insufficient balance. Available: {current_balance}")
#             new_balance = current_balance - amount
#             principal_investment = Decimal('0.00')
#             returns = Decimal('0.00')
#             withdrawal = amount
            
#             # Create new ledger entry
#             ledger_entry = UserLedger.objects.create(
#                 transaction=transaction,
#                 project_name=project.project_name,
#                 principal_investment=principal_investment,
#                 returns=returns,
#                 withdrawal=withdrawal,
#                 balance=new_balance,
#                 date=timezone.now()
#             )
#         else:
#             new_balance = current_balance
#             principal_investment = Decimal('0.00')
#             returns = Decimal('0.00')
#             withdrawal = Decimal('0.00')
            
#             # Create new ledger entry
#             ledger_entry = UserLedger.objects.create(
#                 transaction=transaction,
#                 project_name=project.project_name,
#                 principal_investment=principal_investment,
#                 returns=returns,
#                 withdrawal=withdrawal,
#                 balance=new_balance,
#                 date=timezone.now()
#             )
        
#         print(f"DEBUG: Created ledger entry:")
#         print(f"DEBUG: Transaction type: {transaction_type}")
#         print(f"DEBUG: Amount: {amount}")
#         print(f"DEBUG: Return amount: {return_amount if transaction_type == 'investment' else 'N/A'}")
#         print(f"DEBUG: Previous balance: {current_balance}")
#         print(f"DEBUG: New balance: {new_balance}")
        
#         return transaction, ledger_entry
        
#     except Exception as e:
#         print(f"Error creating transaction: {str(e)}")
#         raise


# from decimal import Decimal
# from django.utils.timezone import now
# from datetime import timedelta
# from dateutil.relativedelta import relativedelta
# from django.core.exceptions import ValidationError

# # Define return periods dynamically
# RETURN_PERIODS = {
#     '2m':  Decimal('525600') / Decimal('2'),   # 2-minute intervals in a year
#     '10m': Decimal('525600') / Decimal('10'),  # 10-minute intervals in a year
#     'monthly': Decimal('12'),                  # 12 months in a year
#     'quarterly': Decimal('4'),                 # 4 quarters in a year
#     'semiannual': Decimal('2'),                # 2 halves in a year
#     'annual': Decimal('1')                     # 1 return per year
# }

# def update_user_ledger(transaction):
#     """Updates the user's ledger when an investment or withdrawal is made."""
#     last_ledger = UserLedger.objects.filter(
#         transaction__user=transaction.user,
#         project_name=transaction.project.project_name
#     ).order_by('-date').first()
    
#     last_balance = last_ledger.balance if last_ledger else Decimal('0.00')
#     print(f"DEBUG: Updating ledger for {transaction.project.project_name}. Last balance: {last_balance}")
    
#     if transaction.transaction_type == 'investment':
#         try:
#             assigned_project = AssignedProject.objects.get(
#                 user=transaction.user,
#                 project=transaction.project
#             )
            
#             new_balance = last_balance  # Keep balance unchanged initially
#             UserLedger.objects.create(
#                 transaction=transaction,
#                 date=now(),
#                 project_name=transaction.project.project_name,
#                 principal_investment=transaction.amount,
#                 returns=Decimal('0.00'),
#                 withdrawal=Decimal('0.00'),
#                 balance=new_balance,
#             )
#         except AssignedProject.DoesNotExist:
#             raise ValidationError(f"No project assignment found for {transaction.user} in {transaction.project}")

#     elif transaction.transaction_type == 'withdrawal':
#         if last_balance < transaction.amount:
#             raise ValidationError("Insufficient balance for withdrawal.")
        
#         new_balance = last_balance - transaction.amount
#         UserLedger.objects.create(
#             transaction=transaction,
#             date=now(),
#             project_name=transaction.project.project_name,
#             principal_investment=Decimal('0.00'),
#             returns=Decimal('0.00'),
#             withdrawal=transaction.amount,
#             balance=new_balance,
#         )

# def generate_missed_returns():
#     print("\n=== DEBUG: Starting generate_missed_returns() ===")
    
#     # Get all approved investment transactions
#     approved_investments = Transaction.objects.filter(
#         transaction_type='investment',
#         status='approved'
#     ).select_related('user', 'project')
    
#     print(f"DEBUG: Found {approved_investments.count()} approved investment transactions")
    
#     for transaction in approved_investments:
#         print(f"\nDEBUG: Processing transaction {transaction.id} for user {transaction.user.username}")
#         print(f"DEBUG: Project: {transaction.project.project_name}")
        
#         # Get assigned project details
#         assigned_project = AssignedProject.objects.filter(
#             user=transaction.user,
#             project=transaction.project
#         ).first()
        
#         if not assigned_project:
#             print(f"DEBUG: No assigned project found for transaction {transaction.id}")
#             continue
            
#         print(f"DEBUG: Found assigned project:")
#         print(f"DEBUG: Return period: {assigned_project.return_period}")
#         print(f"DEBUG: Rate of interest: {assigned_project.rate_of_interest}")
        
#         # Get the return period in minutes
#         return_period_minutes = {
#             '2m': 2,
#             '5m': 5,
#             '10m': 10,
#             '15m': 15,
#             '30m': 30,
#             '1h': 60
#         }.get(assigned_project.return_period, 2)
        
#         print(f"DEBUG: Return period in minutes: {return_period_minutes}")
        
#         # Get all ledger entries for this project in chronological order
#         ledger_entries = UserLedger.objects.filter(
#             transaction__user=transaction.user,
#             project_name=transaction.project.project_name
#         ).order_by('date')
        
#         if not ledger_entries:
#             print(f"DEBUG: No ledger entries found for transaction {transaction.id}")
#             continue
            
#         current_date = transaction.transaction_date
        
#         while current_date < timezone.now():
#             next_date = current_date + timedelta(minutes=return_period_minutes)
            
#             if next_date > timezone.now():
#                 break
                
#             # Check if return already exists for this period
#             existing_return = UserLedger.objects.filter(
#                 transaction__user=transaction.user,
#                 project_name=transaction.project.project_name,
#                 date=next_date,
#                 returns__gt=0
#             ).first()
            
#             if existing_return:
#                 print(f"DEBUG: Return already exists for period {next_date}")
#                 current_date = next_date
#                 continue
            
#             # Get the last balance from any entry before this return
#             last_balance = UserLedger.objects.filter(
#                 transaction__user=transaction.user,
#                 project_name=transaction.project.project_name,
#                 date__lt=next_date
#             ).order_by('-date').first()
            
#             current_balance = last_balance.balance if last_balance else Decimal('0.00')
            
#             # Calculate return based on investment amount and rate
#             rate = assigned_project.rate_of_interest
#             periodic_rate = (rate / Decimal('100.0')) * (Decimal(str(return_period_minutes)) / (Decimal('365.0') * Decimal('24.0') * Decimal('60.0')))
#             return_amount = transaction.amount * periodic_rate
#             return_amount = return_amount.quantize(Decimal('0.01'))
            
#             new_balance = current_balance + return_amount
            
#             # Create new ledger entry for the return
#             new_ledger = UserLedger.objects.create(
#                 transaction=transaction,
#                 project_name=transaction.project.project_name,
#                 principal_investment=transaction.amount,
#                 returns=return_amount,
#                 withdrawal=Decimal('0.00'),
#                 balance=new_balance,
#                 date=next_date
#             )
            
#             print(f"DEBUG: Created return entry:")
#             print(f"DEBUG: Date: {next_date}")
#             print(f"DEBUG: Investment amount: {transaction.amount}")
#             print(f"DEBUG: Rate: {rate}%")
#             print(f"DEBUG: Periodic rate: {periodic_rate}")
#             print(f"DEBUG: Return amount: {return_amount}")
#             print(f"DEBUG: Previous balance: {current_balance}")
#             print(f"DEBUG: New balance: {new_balance}")
            
#             current_date = next_date
    
#     print("=== End generate_missed_returns() ===\n")



# dddd
# dfg
# ghj
# jk
# sdfg
