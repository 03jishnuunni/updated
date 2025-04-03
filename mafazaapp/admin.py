from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AssignedProject, CustomUser,InvestmentProject

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_staff', 'is_approved', 'is_superuser', 'status', 'created_at')
    list_filter = ('is_staff', 'is_superuser', 'status')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Approval & Status", {"fields": ("is_approved", "status")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "is_staff", "is_superuser", "is_approved", "status"),
        }),
    )

    

admin.site.register(CustomUser, CustomUserAdmin)

from django import forms

class AssignedProjectForm(forms.ModelForm):
    class Meta:
        model = AssignedProject
        fields = '__all__'

@admin.register(AssignedProject)
class AssignedProjectAdmin(admin.ModelAdmin):
    form = AssignedProjectForm
    list_display = ('user', 'project', 'rate_of_interest', 'return_period', 'assigned_at')
    list_filter = ('return_period', 'assigned_at')
    search_fields = ('user__username', 'project__project_name')

admin.site.register(InvestmentProject)


from django import forms
from .models import Transaction, AssignedProject

class TransactionAdminForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Filter projects based on assigned projects for the selected user
        if 'user' in self.data:
            user_id = self.data.get('user')
            assigned_projects = AssignedProject.objects.filter(user_id=user_id).values_list('project', flat=True)
            self.fields['project'].queryset = self.fields['project'].queryset.filter(id__in=assigned_projects)
        elif self.instance and self.instance.user:
            assigned_projects = AssignedProject.objects.filter(user=self.instance.user).values_list('project', flat=True)
            self.fields['project'].queryset = self.fields['project'].queryset.filter(id__in=assigned_projects)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    form = TransactionAdminForm
    list_display = ('user', 'project', 'amount', 'transaction_type', 'status', 'transaction_date','return_amount')
    list_filter = ('status', 'transaction_type', 'transaction_date')
    search_fields = ('user__username', 'project__project_name')