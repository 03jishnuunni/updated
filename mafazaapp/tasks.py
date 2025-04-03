# from celery import shared_task
# from django.utils import timezone
# from decimal import Decimal
# from .models import Transaction, AssignedProject
# import logging

# logger = logging.getLogger(__name__)

# @shared_task
# def update_transaction_returns():
#     # Fetch all transactions with a return period of 1 minute and status 'approved'
#     transactions = Transaction.objects.filter(return_period='1m', status='approved')
#     logger.info(f"Found {transactions.count()} transactions to process.")

#     for transaction in transactions:
#         # Calculate the elapsed time since the last transaction
#         elapsed_time = timezone.now() - transaction.transaction_date
#         elapsed_minutes = int(elapsed_time.total_seconds() / 60)
#         logger.info(f"Transaction {transaction.id}: Elapsed time = {elapsed_minutes} minutes.")

#         if elapsed_minutes >= 1:
#             # Get the assigned project details
#             assigned_project = AssignedProject.objects.filter(
#                 user=transaction.user,
#                 project=transaction.project
#             ).first()

#             if assigned_project:
#                 # Calculate the return amount
#                 rate_of_interest = Decimal(assigned_project.rate_of_interest) / Decimal('100')
#                 return_amount = transaction.amount * rate_of_interest
#                 logger.info(f"Transaction {transaction.id}: Calculated return amount = {return_amount}.")

#                 # Create a new transaction for the return
#                 new_transaction = Transaction(
#                     user=transaction.user,
#                     project=transaction.project,
#                     amount=return_amount,
#                     transaction_type='withdrawal',  # Assuming returns are withdrawals
#                     status='approved',
#                     return_period='1m',  # Keep the return period as '1m'
#                     return_amount=return_amount,
#                     transaction_date=timezone.now()
#                 )
#                 new_transaction.save()
#                 logger.info(f"Transaction {transaction.id}: Created new transaction {new_transaction.id}.")

#                 # Update the original transaction's transaction_date to now
#                 transaction.transaction_date = timezone.now()
#                 transaction.save()
#                 logger.info(f"Transaction {transaction.id}: Updated transaction_date to {transaction.transaction_date}.")
#             else:
#                 logger.warning(f"Transaction {transaction.id}: No assigned project found.")
#         else:
#             logger.info(f"Transaction {transaction.id}: Elapsed time is less than 1 minute.")


from celery import shared_task
from django.utils import timezone
from decimal import Decimal, ROUND_DOWN
import logging
from .models import Transaction, AssignedProject
from .views import calculate_return

logger = logging.getLogger(__name__)

@shared_task
def update_transaction_returns():
    # Fetch all active transactions with a return period of 1 minute
    transactions = Transaction.objects.filter(return_period='1m', status='approved')
    logger.info(f"Found {transactions.count()} transactions to process.")

    for transaction in transactions:
        # Calculate the elapsed time since the last update
        elapsed_time = timezone.now() - transaction.transaction_date
        elapsed_minutes = int(elapsed_time.total_seconds() / 60)
        logger.info(f"Transaction {transaction.id}: Elapsed time = {elapsed_minutes} minutes.")

        if elapsed_minutes >= 1:
            # Calculate the new return amount for this transaction
            return_amount = calculate_return(transaction)
            logger.info(f"Transaction {transaction.id}: Calculated return amount = {return_amount}.")

            # Update the transaction's return amount incrementally
            if transaction.return_amount:
                transaction.return_amount += return_amount
            else:
                transaction.return_amount = return_amount

            # Update the transaction date to the current time
            transaction.transaction_date = timezone.now()
            transaction.save()
            logger.info(f"Transaction {transaction.id}: Updated return amount and transaction date.")
        else:
            logger.info(f"Transaction {transaction.id}: Elapsed time is less than 1 minute.")