from django.urls import path

from django.contrib.auth.views import LogoutView

from mafazaapp.views import Adminuser, Home, Myproject,  admin_ledger, admin_view_user_documents,  assign_project, change_password,  create_transaction_view,  custom_login, delete_document, edit_profile,  forgot_password,investment_projects, ledger_view, pending_approval, project_list, reset_password, signup,staff_dashboard, staff_profile, staff_transactions_view, toggle_project_status, update_transaction_status, upload_document, upload_receipt, user_logout, view_documents, download_ledger_pdf, check_upcoming_returns, download_staff_transactions_pdf, download_staff_transactions_csv



urlpatterns = [
    path("",Home,name="home"),
    path('signup/', signup, name='signup'),
    path('login/', custom_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('project_list/',project_list , name='project_list'),
    path("projects/", investment_projects, name="investment_projects"),
    path('assign_project/<uuid:user_id>/', assign_project, name='assign_project'),
    path("staff_dashboard/",staff_dashboard,name="staff_dashboard"),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('change-password/', change_password, name='change_password'),
    path('documents/delete/<int:doc_id>/', delete_document, name='delete_document'),
    path('pend',staff_transactions_view, name='pend'),
    path('staff_profile/',staff_profile, name='staff_profile'),
    path('upload_receipt/<int:transaction_id>/', upload_receipt, name='upload_receipt'),
    path('transactions/', create_transaction_view, name='create_transaction'),
    path('ledger/', ledger_view, name='ledger_view'),
    path('ledger/download-pdf/', download_ledger_pdf, name='download_ledger_pdf'),
    path("admin_user/", Adminuser, name="admin_user"),
    path("admin_ledger/", admin_ledger, name="admin_ledger"),
    path('documents/', view_documents, name='view_documents'),
    path('documents/upload/', upload_document, name='upload_document'),
    path('user/<uuid:user_id>/documents/', admin_view_user_documents, name='admin_user_documents'),
    path('update_transaction/<int:transaction_id>/<str:status>/', update_transaction_status, name='update_transaction_status'),
    path('pending-approval/', pending_approval, name='pending_approval'),
    path('list_project/', Myproject, name='list_project'),
    path('toggle-project-status/<int:project_id>/', toggle_project_status, name='toggle_project_status'),
    path('edit-profile/', edit_profile, name='edit_profile'),
    path('reset-password/<str:token>/', reset_password, name='reset_password'),
    path('check-upcoming-returns/', check_upcoming_returns, name='check_upcoming_returns'),
    path('staff/transactions/pdf/', download_staff_transactions_pdf, name='staff_transactions_pdf'),
    path('staff/transactions/csv/', download_staff_transactions_csv, name='staff_transactions_csv'),
    # path('test/', test, name='test'),
     
   
    
]
   

    

