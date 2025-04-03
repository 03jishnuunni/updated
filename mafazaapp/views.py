from datetime import timezone, timedelta
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Avg, Q
from django.forms import DecimalField, ValidationError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import secrets
import string
import logging
from django.views.decorators.csrf import csrf_protect
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime
import csv
from reportlab.pdfgen import canvas

from mafaza__project import settings

from .forms import (
    CustomUserCreationForm, InvestmentProjectForm, AssignProjectForm,
    PasswordEditForm, StaffTransactionForm, UserEditForm, TransactionForm,
    PasswordChangeForm, DocumentUploadForm
)
from .models import (
    AssignedProject, InvestmentProject, CustomUser, PasswordResetToken,
    Transaction, UserLedger, UserDocument
)
from .utils import create_transaction, generate_missed_returns
from .validators import (
    validate_investment_amount,
    validate_withdrawal_amount,
    validate_receipt_file,
    validate_transaction_rate_limit,
    validate_project_status
)

# Set up logging
logger = logging.getLogger(__name__)

def Home(request):
    projects = InvestmentProject.objects.filter(is_active=True)  
    return render(request, "home.html", {"projects": projects})

# def test(request):
    
#     return render(request, "softui.html")

def user_logout(request):
    logout(request)
    request.session.flush()  # Clear all session data

    response = redirect('login')  # Redirect to login page
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response

@csrf_protect
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.status = 'PENDING'
                user.save()
                
                # Send welcome email
                try:
                    send_welcome_email(user)
                except Exception as e:
                    # Log the error but don't prevent signup
                    print(f"Failed to send welcome email: {str(e)}")
                
                messages.success(request, 'Account created successfully! Please check your email to verify your account.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'An error occurred while creating your account. Please try again.')
                print(f"Signup error: {str(e)}")
        else:
            # Log form errors for debugging
            print("Form errors:", form.errors)
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    context = {
        'form': form,
        'request': request,
        'debug': settings.DEBUG,  # Add debug flag to context
    }
    return render(request, 'signup.html', context)

def pending_approval(request):
    return render(request, 'pending_approval.html')

def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip().lower()  # Normalize username
        password = request.POST.get('password', '').strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Account is inactive. Please contact admin.")
                logger.warning(f"Inactive account login attempt: {username}")
                return render(request, 'login.html')

            if hasattr(user, 'status') and user.status == "PENDING":
                messages.info(request, "Your account is pending approval.")
                return redirect('pending_approval')

            login(request, user)
            logger.info(f"Successful login: {username}")
            return redirect('staff_dashboard' if user.is_staff else 'ledger_view')

        else:
            messages.error(request, "Invalid username or password")
            logger.warning(f"Failed login attempt for username: {username}")

    return render(request, 'login.html')

@login_required(login_url="/login/")
def investment_projects(request):
   
    projects_list = InvestmentProject.objects.all().order_by('-id')  

 
    paginator = Paginator(projects_list, 4)
    page = request.GET.get('page') 

    try:
        projects = paginator.page(page)
    except PageNotAnInteger:
        
        projects = paginator.page(1)
    except EmptyPage:
      
        projects = paginator.page(paginator.num_pages)

    
    form = InvestmentProjectForm()
    if request.method == "POST":
        form = InvestmentProjectForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Project added successfully!")
            return redirect("investment_projects")  

    return render(request, "Admin/investment_projects.html", {"projects": projects, "form": form})

def project_list(request):
    projects = InvestmentProject.objects.filter(is_active=True) 
    return render(request, "Admin/project_list.html", {"projects": projects})

@login_required
@staff_member_required
def assign_project(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    projects = InvestmentProject.objects.filter(is_active=True).exclude(
        id__in=user.assigned_projects.values_list('project_id', flat=True)
    )
    assigned_projects = user.assigned_projects.select_related('project').all()

    if request.method == "POST":
        if 'project_id' in request.POST:  # New assignment
            project_id = request.POST.get("project_id")
            return_period = request.POST.get("return_period")
            rate_of_interest = request.POST.get("rate_of_interest")

            project = get_object_or_404(InvestmentProject, id=project_id)

            assigned, created = AssignedProject.objects.get_or_create(
                user=user,
                project=project,
                defaults={
                    'return_period': return_period,
                    'rate_of_interest': rate_of_interest
                }
            )

            if not created:
                return render(request, "assign_project_form.html", {
                    "user": user,
                    "projects": projects,
                    "assigned_projects": assigned_projects,
                    "error": "Project already assigned to user!"
                })

            return redirect("admin_user")

        elif 'edit_id' in request.POST:  # Edit existing assignment
            assigned_id = request.POST.get("edit_id")
            new_roi = request.POST.get("new_roi")
            new_period = request.POST.get("new_period")

            assigned = get_object_or_404(AssignedProject, id=assigned_id, user=user)
            assigned.rate_of_interest = new_roi
            assigned.return_period = new_period
            assigned.save()

            return redirect("admin_user")

    return render(request, "assign_project_form.html", {
        "user": user,
        "projects": projects,
        "assigned_projects": assigned_projects
    })

@login_required
@staff_member_required
def staff_dashboard(request):
    assigned_projects = AssignedProject.objects.all()

    # Fetch all transactions ordered by date (newest first)
    all_transactions = Transaction.objects.select_related('user', 'project')\
                                       .all()\
                                       .order_by('-transaction_date')
    
    # Pagination with 2 items per page
    paginator = Paginator(all_transactions, 2)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Calculate dashboard metrics
    total_investments = UserLedger.objects.aggregate(
        Sum('principal_investment')
    )['principal_investment__sum'] or 0
    total_returns = UserLedger.objects.aggregate(Sum('returns'))['returns__sum'] or 0
    total_withdrawals = UserLedger.objects.aggregate(Sum('withdrawal'))['withdrawal__sum'] or 0
    total_projects = InvestmentProject.objects.count()
    total_roi = AssignedProject.objects.aggregate(
        Avg('rate_of_interest')
    )['rate_of_interest__avg'] or 0

    context = {
        "assigned_projects": assigned_projects,
        "page_obj": page_obj,  # This is the paginated data
        "total_investments": total_investments,
        "total_returns": total_returns,
        "total_withdrawals": total_withdrawals,
        "total_projects": total_projects,
        "total_roi": total_roi,
    }
    return render(request, "Admin/staff_dashboard.html", context)

@login_required
@staff_member_required
def update_transaction_status(request, transaction_id, status):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    print("\n=== DEBUG: Processing Transaction Status Update ===")
    print(f"DEBUG: Transaction ID: {transaction_id}")
    print(f"DEBUG: New Status: {status}")
    print(f"DEBUG: Transaction Type: {transaction.transaction_type}")
    print(f"DEBUG: Amount: {transaction.amount}")
    print(f"DEBUG: Project: {transaction.project.project_name}")
    print(f"DEBUG: User: {transaction.user.username}")
    print(f"DEBUG: Current Status: {transaction.status}")
    
    if status in ['approved', 'rejected']:
        transaction.status = status
        transaction.save()
        print(f"DEBUG: Transaction status updated to {status}")
        
        if status == 'approved':
            if transaction.transaction_type == 'investment':
                print("\n=== DEBUG: Processing Investment Approval ===")
                try:
                    # Get the latest ledger entry for this project
                    last_ledger = UserLedger.objects.filter(
                        transaction__user=transaction.user,
                        project_name=transaction.project.project_name
                    ).order_by('-date').first()
                    
                    print(f"DEBUG: Last ledger entry: {last_ledger}")
                    if last_ledger:
                        print(f"DEBUG: Last ledger balance: {last_ledger.balance}")
                        print(f"DEBUG: Last ledger date: {last_ledger.date}")
                    
                    # Create new ledger entry for the investment
                    ledger_entry = UserLedger.objects.create(
                        transaction=transaction,
                        project_name=transaction.project.project_name,
                        principal_investment=transaction.amount,
                        returns=Decimal('0.00'),  # No returns yet
                        withdrawal=Decimal('0.00'),
                        balance=Decimal('0.00'),  # Set initial balance to 0
                        date=timezone.now()  # Use approval time
                    )
                    
                    print(f"DEBUG: Created ledger entry:")
                    print(f"DEBUG: Entry ID: {ledger_entry.id}")
                    print(f"DEBUG: Date: {ledger_entry.date}")
                    print(f"DEBUG: Balance: {ledger_entry.balance}")
                    
                    # Update transaction date to match approval time
                    transaction.transaction_date = timezone.now()
                    transaction.save()
                    
                    # Generate missed returns immediately after approval
                    print("\nDEBUG: Calling generate_missed_returns()")
                    generate_missed_returns()
                    
                    print("=== End Investment Approval ===\n")
                    messages.success(request, f"Investment approved and ledger entry created for transaction {transaction.id}")
                except Exception as e:
                    print(f"DEBUG: ERROR creating ledger entry: {str(e)}")
                    messages.error(request, f"Error creating ledger entry: {str(e)}")
                    logger.error(f"Error creating ledger entry for transaction {transaction.id}: {str(e)}")
            elif transaction.transaction_type == 'withdrawal':
                print("\n=== DEBUG: Processing Withdrawal Approval ===")
                try:
                    # Get the latest ledger entry
                    last_ledger = UserLedger.objects.filter(
                        transaction__user=transaction.user,
                        project_name=transaction.project.project_name
                    ).order_by('-date').first()
                    
                    print(f"DEBUG: Last ledger entry: {last_ledger}")
                    if last_ledger:
                        print(f"DEBUG: Last ledger balance: {last_ledger.balance}")
                    
                    if last_ledger and last_ledger.balance >= transaction.amount:
                        # Create withdrawal ledger entry
                        ledger_entry = UserLedger.objects.create(
                            transaction=transaction,
                            project_name=transaction.project.project_name,
                            principal_investment=Decimal('0.00'),
                            returns=Decimal('0.00'),
                            withdrawal=transaction.amount,
                            balance=last_ledger.balance - transaction.amount,
                            date=timezone.now()  # Use approval time
                        )
                        print(f"DEBUG: Created withdrawal ledger entry:")
                        print(f"DEBUG: Entry ID: {ledger_entry.id}")
                        print(f"DEBUG: New balance: {ledger_entry.balance}")
                        
                        # Update transaction date to match approval time
                        transaction.transaction_date = timezone.now()
                        transaction.save()
                        
                        # Generate missed returns after withdrawal
                        print("\nDEBUG: Calling generate_missed_returns() after withdrawal")
                        generate_missed_returns()
                        
                        print("=== End Withdrawal Approval ===\n")
                        messages.success(request, f"Withdrawal approved and ledger entry created for transaction {transaction.id}")
                    else:
                        print(f"DEBUG: ERROR - Insufficient balance")
                        print(f"DEBUG: Current balance: {last_ledger.balance if last_ledger else 0}")
                        print(f"DEBUG: Required amount: {transaction.amount}")
                        messages.error(request, "Insufficient balance for withdrawal")
                        transaction.status = 'rejected'
                        transaction.save()
                except Exception as e:
                    print(f"DEBUG: ERROR processing withdrawal: {str(e)}")
                    messages.error(request, f"Error processing withdrawal: {str(e)}")
                    logger.error(f"Error processing withdrawal for transaction {transaction.id}: {str(e)}")
        else:
            print(f"DEBUG: Transaction {transaction.id} rejected")
            messages.success(request, f"Transaction {transaction.id} rejected.")
    
    print("=== End Transaction Status Update ===\n")
    return redirect("staff_dashboard")

def upload_receipt(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)

    if transaction.transaction_type == "withdrawal":
        # Withdrawal requires receipt
        if request.method == "POST" and request.FILES.get("receipt"):
            receipt_file = request.FILES["receipt"]
            
            try:
                # Validate receipt file
                validate_receipt_file(receipt_file)
                
                # Get the latest ledger entry
                last_ledger = UserLedger.objects.filter(
                    transaction__user=transaction.user,
                    project_name=transaction.project.project_name
                ).order_by('-date').first()
                
                print(f"DEBUG: Processing withdrawal approval with receipt")
                print(f"DEBUG: Last ledger entry: {last_ledger}")
                if last_ledger:
                    print(f"DEBUG: Last ledger balance: {last_ledger.balance}")
                
                if last_ledger and last_ledger.balance >= transaction.amount:
                    # Create withdrawal ledger entry
                    ledger_entry = UserLedger.objects.create(
                        transaction=transaction,
                        project_name=transaction.project.project_name,
                        principal_investment=Decimal('0.00'),
                        returns=Decimal('0.00'),
                        withdrawal=transaction.amount,
                        balance=last_ledger.balance - transaction.amount,
                        date=timezone.now(),  # Use approval time
                        receipt=receipt_file
                    )
                    print(f"DEBUG: Created withdrawal ledger entry:")
                    print(f"DEBUG: Entry ID: {ledger_entry.id}")
                    print(f"DEBUG: New balance: {ledger_entry.balance}")
                    
                    # Update transaction status and receipt
                    transaction.receipt = receipt_file
                    transaction.status = "approved"
                    transaction.transaction_date = timezone.now()
                    transaction.save()
                    
                    # Generate missed returns after withdrawal
                    print("\nDEBUG: Calling generate_missed_returns() after withdrawal")
                    generate_missed_returns()
                    
                    messages.success(request, "Withdrawal approved and receipt uploaded successfully!")
                else:
                    print(f"DEBUG: ERROR - Insufficient balance")
                    print(f"DEBUG: Current balance: {last_ledger.balance if last_ledger else 0}")
                    print(f"DEBUG: Required amount: {transaction.amount}")
                    messages.error(request, "Insufficient balance for withdrawal")
                    transaction.status = 'rejected'
                    transaction.save()
            except ValidationError as e:
                print(f"DEBUG: Validation Error: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                print(f"DEBUG: ERROR processing withdrawal: {str(e)}")
                messages.error(request, f"Error processing withdrawal: {str(e)}")
                logger.error(f"Error processing withdrawal for transaction {transaction.id}: {str(e)}")
        else:
            messages.error(request, "Receipt is required for withdrawal approval.")
        
    else:
        # Investment approval (No receipt required)
        transaction.status = "approved"
        transaction.save()
        messages.success(request, "Investment approved successfully!")

    return redirect("ledger_view")

@login_required(login_url="/login/")
def investment_projects(request):
   
    projects_list = InvestmentProject.objects.all().order_by('-id')  

 
    paginator = Paginator(projects_list, 4)
    page = request.GET.get('page') 

    try:
        projects = paginator.page(page)
    except PageNotAnInteger:
        
        projects = paginator.page(1)
    except EmptyPage:
      
        projects = paginator.page(paginator.num_pages)

    
    form = InvestmentProjectForm()
    if request.method == "POST":
        form = InvestmentProjectForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Project added successfully!")
            return redirect("investment_projects") 

    return render(request, "Admin/investment_projects.html", {"projects": projects, "form": form})

def toggle_project_status(request, project_id):
   
    project = get_object_or_404(InvestmentProject, id=project_id)
  
    project.is_active = not project.is_active
    project.save()
    
    
    messages.success(request, f"Project '{project.project_name}' is now {'active' if project.is_active else 'inactive'}.")
    
    
    return redirect('investment_projects')
@login_required
def Myproject(request):
  
    user = request.user
    
  
    active_projects = InvestmentProject.objects.filter(is_active=True)
    
   
    user_invested_projects = InvestmentProject.objects.filter(
        transactions__user=user  
    ).distinct()

   

    
    return render(request, "User/list_projects.html", {
        "active_projects": active_projects,
        "user_invested_projects": user_invested_projects
    })

@login_required
@staff_member_required
def admin_ledger(request):
    # Get base queryset
    ledger_entries = UserLedger.objects.select_related('transaction__user').all().order_by('-date')
    
    # Filter by user type if specified
    user_type = request.GET.get('user_type', '')
    if user_type:
        ledger_entries = ledger_entries.filter(transaction__user__groups__name=user_type)
    
    # Add pagination with 50 items per page
    paginator = Paginator(ledger_entries, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "admin_ledger.html", {
        "page_obj": page_obj,  # Changed from ledger_entries to page_obj
        "user_type": user_type
    })

@login_required
@staff_member_required
def admin_view_user_documents(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    documents = UserDocument.objects.filter(user=user).order_by('-uploaded_at')
    
    return render(request, 'Admin/admin_document_list.html', {
        'user': user,
        'documents': documents
    })

@login_required(login_url='login')
def create_transaction_view(request):
    projects = AssignedProject.objects.filter(user=request.user)
    current_balance = Decimal('0.00')
    transactions = Transaction.objects.filter(user=request.user).order_by('-transaction_date')

    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES, user=request.user)
        
        if form.is_valid():
            try:
                project = form.cleaned_data['project']
                amount = form.cleaned_data['amount']
                transaction_type = form.cleaned_data['transaction_type']
                
                print("\n=== DEBUG: Creating New Transaction ===")
                print(f"DEBUG: User: {request.user.username}")
                print(f"DEBUG: Project: {project.project_name}")
                print(f"DEBUG: Amount: {amount}")
                print(f"DEBUG: Type: {transaction_type}")
                
                # Validate project status
                validate_project_status(project)
                
                # Validate transaction rate limit
                validate_transaction_rate_limit(request.user)
                
                # Get assigned project details
                assigned_project = AssignedProject.objects.filter(
                    user=request.user,
                    project=project
                ).first()
                
                if not assigned_project:
                    print("DEBUG: ERROR - No assigned project found!")
                    messages.error(request, "No project assignment found!")
                    return redirect('ledger_view')
                
                print(f"DEBUG: Found assigned project:")
                print(f"DEBUG: Return period: {assigned_project.return_period}")
                print(f"DEBUG: Rate of interest: {assigned_project.rate_of_interest}")
                
                # Validate amount based on transaction type
                if transaction_type == 'investment':
                    validate_investment_amount(amount)
                elif transaction_type == 'withdrawal':
                    # Get current balance for this project
                    last_ledger = UserLedger.objects.filter(
                        transaction__user=request.user,
                        project_name=project.project_name
                    ).order_by('-date').first()
                    
                    available_balance = last_ledger.balance if last_ledger else Decimal('0.00')
                    print(f"DEBUG: Available balance: {available_balance}")
                    
                    if amount > available_balance:
                        print(f"DEBUG: ERROR - Insufficient balance")
                        print(f"DEBUG: Required amount: {amount}")
                        print(f"DEBUG: Available balance: {available_balance}")
                        messages.error(request, f"Insufficient balance. Available balance: {available_balance}")
                        return redirect('ledger_view')
                    
                    if amount <= Decimal('0.00'):
                        print("DEBUG: ERROR - Withdrawal amount must be greater than 0")
                        messages.error(request, "Withdrawal amount must be greater than 0")
                        return redirect('ledger_view')
                
                # Create transaction
                transaction = form.save(commit=False)
                transaction.user = request.user
                transaction.status = 'pending'
                transaction.save()
                
                print(f"DEBUG: Transaction created successfully:")
                print(f"DEBUG: Transaction ID: {transaction.id}")
                print(f"DEBUG: Status: {transaction.status}")
                print(f"DEBUG: Date: {transaction.transaction_date}")
                print("=== End Transaction Creation ===\n")
                
                messages.success(request, 'Transaction created successfully! Waiting for staff approval.')
                return redirect('ledger_view')
                
            except ValidationError as e:
                print(f"DEBUG: Validation Error: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                print(f"DEBUG: ERROR creating transaction: {str(e)}")
                messages.error(request, f'Error: {str(e)}')
    else:
        form = TransactionForm(user=request.user)
        last_ledger = UserLedger.objects.filter(
            transaction__user=request.user
        ).order_by('-date').first()
        current_balance = last_ledger.balance if last_ledger else Decimal('0.00')

    return render(request, 'transactions.html', {
        'form': form,
        'projects': projects,
        'current_balance': current_balance,
        'transactions': transactions
    })

@login_required(login_url='login')
def ledger_view(request):
    generate_missed_returns()

    # Get all approved transactions in chronological order (oldest first)
    ledger_entries = UserLedger.objects.filter(
        transaction__user=request.user,
        transaction__status='approved'
    ).order_by('date')  # Changed from '-date' to 'date' to show oldest first

    # Add pagination - 50 items per page
    paginator = Paginator(ledger_entries, 50)
    page_number = request.GET.get('page', 1)  # Default to page 1 if no page number provided
    
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        # If page is not an integer or is out of range, deliver first page
        page_obj = paginator.page(1)

    projects = AssignedProject.objects.filter(user=request.user)
    
    total_investment = UserLedger.objects.filter(
        transaction__user=request.user,
        principal_investment__gt=0
    ).aggregate(total=Sum('principal_investment'))['total'] or Decimal('0.00')

    total_balance = Decimal('0.00')
    for project in projects:
        latest_ledger = UserLedger.objects.filter(
            transaction__user=request.user,
            project_name=project.project.project_name
        ).order_by('-date').first()
        if latest_ledger:
            total_balance += latest_ledger.balance

    avg_interest_rate = projects.aggregate(
        avg_rate=Avg('rate_of_interest')
    )['avg_rate'] or 0

    total_projects = projects.count()

    total_withdrawals = UserLedger.objects.filter(
        transaction__user=request.user,
        withdrawal__gt=0
    ).aggregate(total=Sum('withdrawal'))['total'] or Decimal('0.00')

    context = {
        'page_obj': page_obj,
        'total_investment': total_investment,
        'total_balance': total_balance,
        'avg_interest_rate': avg_interest_rate,
        'total_projects': total_projects,
        'total_withdrawals': total_withdrawals,
    }

    return render(request, 'ledger.html', context)



@login_required
def edit_profile(request):
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)

        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('ledger_view')

    else:
        user_form = UserEditForm(instance=request.user)

    return render(request, 'User/edit_profile.html', {
        'user_form': user_form,
    })
@login_required
@staff_member_required   
def staff_profile(request):
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=request.user)

        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('ledger_view')

    else:
        user_form = UserEditForm(instance=request.user)

    return render(request, 'Admin/staff_profile.html', {
        'user_form': user_form,
    })    
    
    

@login_required
@staff_member_required
def Adminuser(request):
    if not request.user.is_staff:
        return redirect('login')
    
    # Get user type filter from GET parameters
    user_type = request.GET.get('user_type', '')
    page_number = request.GET.get('page', 1)

    # Base querysets
    users = CustomUser.objects.filter(Q(is_approved=True) | Q(is_staff=True))
    pending_users = CustomUser.objects.filter(status='PENDING')

    # Apply user type filter if specified
    if user_type:
        if user_type == 'Admin':
            users = users.filter(is_staff=True)
        elif user_type == 'User':
            users = users.filter(is_staff=False)

    # Apply pagination (10 users per page)
    paginator = Paginator(users, 2)
    users_page = paginator.get_page(page_number)

    if request.method == "POST":
        # Handle user approval/rejection
        if 'user_id' in request.POST:
            user_id = request.POST.get("user_id")
            action = request.POST.get("action")
            user = CustomUser.objects.get(id=user_id)
            
            if action == "approve":
                user.is_approved = True
                user.status = "APPROVED"
                user.save()
                messages.success(request, f"User {user.username} approved successfully")
                
            elif action == "reject":
                user.is_approved = False
                user.status = "REJECTED"
                user.save()
                messages.warning(request, f"User {user.username} rejected")
                
            elif action in ["activate", "deactivate"]:
                user.is_active = (action == "activate")
                user.save()
                status = "activated" if user.is_active else "deactivated"
                messages.success(request, f"User {user.username} {status} successfully")
                
            elif action in ["promote", "demote"]:
                user.is_staff = (action == "promote")
                user.save()
                role = "admin" if user.is_staff else "regular user"
                messages.success(request, f"User {user.username} is now a {role}")
            
            return redirect('admin_user')

    return render(request, "Admin/admin_user.html", {
        "users": users_page,  # Use paginated users
        "pending_users": pending_users,
        "user_type": user_type
    })

    
def forgot_password(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        logger.info(f"Password reset requested for username: {username}")
        
        try:
            user = CustomUser.objects.get(username=username)
            
            # Check if user already has a valid reset token
            existing_token = PasswordResetToken.objects.filter(
                user=user,
                used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if existing_token:
                logger.warning(f"User {username} already has a valid reset token")
                messages.info(request, "A password reset link has already been sent to your email.")
                return redirect('login')
            
            # Generate a secure token
            token = secrets.token_urlsafe(32)
            
            # Create password reset token (expires in 1 hour)
            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # Generate reset URL
            reset_url = request.build_absolute_uri(
                reverse('reset_password', args=[token])
            )
            
            # Send email
            subject = 'Password Reset Request'
            message = f'''
            Hello {user.username},
            
            You have requested to reset your password. Click the link below to reset it:
            
            {reset_url}
            
            This link will expire in 1 hour.
            
            If you did not request this password reset, please ignore this email.
            
            Best regards,
            Your Team
            '''
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                logger.info(f"Password reset email sent to {user.email}")
                messages.success(request, "Password reset instructions have been sent to your email.")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {str(e)}")
                messages.error(request, "Failed to send password reset email. Please try again later.")
                reset_token.delete()
                return redirect('login')
            
            return redirect('login')
            
        except CustomUser.DoesNotExist:
            logger.warning(f"Password reset attempted for non-existent user: {username}")
            messages.error(request, "Username not found")
    
    return render(request, 'forgot_password.html')

def reset_password(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
        
        if not reset_token.is_valid():
            logger.warning(f"Invalid or expired reset token attempted: {token}")
            messages.error(request, "This password reset link has expired or already been used.")
            return redirect('login')
            
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not new_password or not confirm_password:
                messages.error(request, "Please fill in all fields.")
            elif new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
            elif len(new_password) < 8:
                messages.error(request, "Password must be at least 8 characters long.")
            else:
                try:
                    # Set new password
                    reset_token.user.set_password(new_password)
                    reset_token.user.save()
                    
                    # Mark token as used
                    reset_token.used = True
                    reset_token.save()
                    
                    logger.info(f"Password successfully reset for user: {reset_token.user.username}")
                    messages.success(request, "Your password has been reset successfully. Please login with your new password.")
                    return redirect('login')
                except Exception as e:
                    logger.error(f"Error resetting password: {str(e)}")
                    messages.error(request, "An error occurred while resetting your password. Please try again.")
                
        return render(request, 'reset_password.html')
        
    except PasswordResetToken.DoesNotExist:
        logger.warning(f"Invalid reset token attempted: {token}")
        messages.error(request, "Invalid password reset link.")
        return redirect('login')

@login_required(login_url='login')
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.POST)
        if form.is_valid():
            current_password = form.cleaned_data['current_password']
            new_password = form.cleaned_data['new_password']
            
            # Verify current password
            if not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect!")
            else:
                request.user.set_password(new_password)
                request.user.save()
                # Keep user logged in after password change
                update_session_auth_hash(request, request.user)  
                messages.success(request, "Password changed successfully!")
                return redirect('login')  # Redirect to profile page
    else:
        form = PasswordChangeForm()
    
    return render(request, 'change_password.html', {'form': form})

def is_staff(user):
    return user.is_staff

@login_required
def upload_document(request):
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.save()
            return redirect('view_documents')
    else:
        form = DocumentUploadForm()
    
    return render(request, 'User/upload.html', {'form': form})

@login_required
def view_documents(request):
    documents = UserDocument.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'User/list.html', {'documents': documents})

@login_required
def delete_document(request, doc_id):
    document = get_object_or_404(UserDocument, id=doc_id, user=request.user)
    
    if request.method == 'POST':
        document.file.delete()  # Delete the actual file
        document.delete()      # Delete the database record
        messages.success(request, 'Document deleted successfully!')
        return redirect('view_documents')
    
    return render(request, 'User/confirm_delete.html', {'document': document})



@login_required
@staff_member_required
def staff_transactions_view(request):
    # Handle transaction creation
    if request.method == 'POST' and 'create_transaction' in request.POST:
        form = StaffTransactionForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.status = 'approved'
            project = form.cleaned_data['project']
            transaction.return_period = 'custom'
            transaction.save()
            messages.success(request, 'Transaction created successfully!')
            return redirect('pend')
    else:
        form = StaffTransactionForm()

    # Get pending transactions with pagination
    pending_transactions = Transaction.objects.filter(status='pending').order_by('-transaction_date')
    paginator = Paginator(pending_transactions, 2)  # Show 10 transactions per page
    page_number = request.GET.get('page')
    pending_page_obj = paginator.get_page(page_number)

    context = {
        'form': form,
        'pending_page_obj': pending_page_obj,
    }
    return render(request, 'pending_transactions.html', context)

@login_required(login_url='login')
def download_ledger_pdf(request):
    # Get ledger entries
    ledger_entries = UserLedger.objects.filter(
        transaction__user=request.user,
        transaction__status='approved'
    ).order_by('date')

    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ledger_{datetime.now().strftime("%Y%m%d")}.pdf"'

    # Create the PDF object, using BytesIO as its "file."
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Add title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    elements.append(Paragraph("Investment Ledger Report", title_style))

    # Prepare table data
    table_data = [['Date', 'Project', 'Investment', 'Returns', 'Withdrawal', 'Balance']]
    
    for entry in ledger_entries:
        table_data.append([
            entry.date.strftime('%Y-%m-%d'),
            entry.project_name,
            str(entry.principal_investment),
            str(entry.returns),
            str(entry.withdrawal),
            str(entry.balance)
        ])

    # Create table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)

    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response

@staff_member_required
def check_upcoming_returns(request):
    try:
        # Get all approved investment transactions
        transactions = Transaction.objects.filter(
            transaction_type='investment',
            status='approved'
        ).select_related('user', 'project')
        
        notifications = []
        now = timezone.now()
        
        for transaction in transactions:
            try:
                # Get the assigned project to get the return period
                assigned_project = AssignedProject.objects.get(user=transaction.user, project=transaction.project)
                
                # Convert return period to minutes
                period_minutes = {
                    '2m': 2,
                    '10m': 10,
                    'monthly': 43200,  # 30 days
                    'quarterly': 129600,  # 90 days
                    'semiannual': 259200,  # 180 days
                    'annual': 518400,  # 360 days
                }.get(assigned_project.return_period, 2)  # Default to 2 minutes if not found
                
                # Calculate next return date based on transaction date and return period
                next_return = transaction.transaction_date + timedelta(minutes=period_minutes)
                
                # Calculate time until next return
                time_diff = next_return - now
                
                # For 2m return period, show notification 30 seconds before
                if assigned_project.return_period == '2m':
                    if timedelta(seconds=0) <= time_diff <= timedelta(seconds=30):
                        notifications.append({
                            'user': transaction.user.get_full_name(),
                            'project': transaction.project.project_name,
                            'amount': str(transaction.amount),
                            'time_left': f"{time_diff.seconds} seconds"
                        })
                else:
                    # For other periods, show notification within 24 hours
                    if timedelta(seconds=0) <= time_diff <= timedelta(hours=24):
                        # Format time left
                        hours = time_diff.total_seconds() // 3600
                        minutes = (time_diff.total_seconds() % 3600) // 60
                        seconds = time_diff.total_seconds() % 60
                        
                        time_left = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                        
                        notifications.append({
                            'user': transaction.user.get_full_name(),
                            'project': transaction.project.project_name,
                            'amount': str(transaction.amount),
                            'time_left': time_left
                        })
            except AssignedProject.DoesNotExist:
                continue  # Skip this transaction if no assigned project exists
        
        return JsonResponse({
            'notifications': notifications,
            'success': True
        })
    except Exception as e:
        logger.error(f"Error in check_upcoming_returns: {str(e)}")
        return JsonResponse({
            'notifications': [],
            'success': False,
            'error': str(e)
        }, status=500)

@staff_member_required
def download_staff_transactions_pdf(request):
    # Get all transactions
    transactions = Transaction.objects.select_related('user', 'project')\
                                   .all()\
                                   .order_by('-transaction_date')

    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="transactions_{datetime.now().strftime("%Y%m%d")}.pdf"'

    # Create the PDF object
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Add title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30
    )
    elements.append(Paragraph("Transactions Report", title_style))

    # Prepare table data
    table_data = [['Date', 'Name', 'Project', 'Debit', 'Credit', 'Status']]
    
    for transaction in transactions:
        debit = transaction.amount if transaction.transaction_type == 'withdrawal' else '-'
        credit = transaction.amount if transaction.transaction_type == 'investment' else '-'
        
        table_data.append([
            transaction.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
            transaction.user.get_full_name(),
            transaction.project.project_name,
            str(debit),
            str(credit),
            transaction.status
        ])

    # Create table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response

@staff_member_required
def download_staff_transactions_csv(request):
    # Create the HttpResponse object with CSV headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{datetime.now().strftime("%Y%m%d")}.csv"'

    # Create CSV writer
    writer = csv.writer(response)
    
    # Write headers
    writer.writerow(['Date', 'Name', 'Project', 'Debit', 'Credit', 'Status'])
    
    # Get all transactions
    transactions = Transaction.objects.select_related('user', 'project')\
                                   .all()\
                                   .order_by('-transaction_date')
    
    # Write data rows
    for transaction in transactions:
        debit = transaction.amount if transaction.transaction_type == 'withdrawal' else ''
        credit = transaction.amount if transaction.transaction_type == 'investment' else ''
        
        writer.writerow([
            transaction.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
            transaction.user.get_full_name(),
            transaction.project.project_name,
            debit,
            credit,
            transaction.status
        ])
    
    return response

