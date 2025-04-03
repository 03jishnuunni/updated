from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser,InvestmentProject
import re
from .models import UserDocument      
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserChangeForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import Transaction, AssignedProject




class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 
                  'phone_number', 'address', 'country', 'password1', 'password2']
        help_texts = {
            'username': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
            'password1': 'Your password must contain at least 8 characters, one uppercase letter, and one number.',
            'password2': 'Enter the same password as before, for verification.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add Bootstrap form-control class and placeholders
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label
            })

            if field_name in ['password1', 'password2']:
                field.widget.attrs.update({
                    'autocomplete': 'new-password',
                    'class': 'form-control password-input'
                })

            if field_name == 'email':
                field.required = True
                field.widget.attrs['autocomplete'] = 'email'

            # Add required field indicator
            if field.required:
                field.label = f"{field.label} *"

    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        if not email:
            raise ValidationError("Email is required.")
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("A user with that email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError("Username is required.")
        if not re.match(r'^[\w.@+-]+$', username):
            raise ValidationError("Username can only contain letters, numbers, and @/./+/-/_ characters.")
        if CustomUser.objects.filter(username=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '').strip()
        if not password:
            raise ValidationError("Password is required.")

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number.")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character.")

        return password

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields didn't match.")

        return cleaned_data



class InvestmentProjectForm(forms.ModelForm):
    class Meta:
        model = InvestmentProject
        fields = ["project_name", "total_investment", "min_roi", "max_roi", "project_description", "image1", "image2", "image3", "is_active"]
        widgets = {
            'project_name': forms.TextInput(attrs={
                'class': 'form-control  border-end-1',
                'placeholder': 'Enter Project Name'
            }),
            'total_investment': forms.NumberInput(attrs={
                'class': 'form-control border-start-1 border-end-1',
                'placeholder': 'Total Investment'
            }),
            'min_roi': forms.NumberInput(attrs={
                'class': 'form-control border-start-1 border-end-1',
                'placeholder': 'Min ROI (%)'
            }),
            'max_roi': forms.NumberInput(attrs={
                'class': 'form-control border-start-1 border-end-1',
                'placeholder': 'Max ROI (%)'
            }),
            'project_description': forms.Textarea(attrs={
                'class': 'form-control rounded p-3 shadow-sm',
                'placeholder': 'Describe your project...',
                'rows': 4
            }),
            'image1': forms.FileInput(attrs={'class': 'form-control shadow-sm'}),
            'image2': forms.FileInput(attrs={'class': 'form-control shadow-sm'}),
            'image3': forms.FileInput(attrs={'class': 'form-control shadow-sm'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'project_name': 'Project Name',
            'total_investment': 'Total Investment',
            'min_roi': 'Minimum ROI (%)',
            'max_roi': 'Maximum ROI (%)',
            'project_description': 'Project Description',
            'image1': 'Image 1',
            'image2': 'Image 2',
            'image3': 'Image 3',
            'is_active': 'Is Active?',
        }
        help_texts = {
            'min_roi': 'Enter the minimum expected return on investment in percentage.',
            'max_roi': 'Enter the maximum expected return on investment in percentage.',
            'image1': 'Upload an image for the project (optional).',
            'image2': 'Upload an additional image (optional).',
            'image3': 'Upload another image (optional).',
        }

    def clean(self):
        cleaned_data = super().clean()
        min_roi = cleaned_data.get('min_roi')
        max_roi = cleaned_data.get('max_roi')

        if min_roi and max_roi and min_roi > max_roi:
            raise forms.ValidationError("Minimum ROI cannot be greater than Maximum ROI.")

        return cleaned_data






class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['project', 'amount', 'transaction_type', 'return_period','narration', 'receipt']
        widgets = {
            #  'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'transaction amount'
            }),
             'narration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'narration'
            }),
              'project': forms.Select(attrs={'class': 'form-control'}),
              'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            #   'receipt': forms.ClearableFileInput(attrs={
            #     'class': 'form-control d-none',  # Hide default input
            #     'id': 'file-upload'
            # }),
            
        }
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Get the user from kwargs
        super().__init__(*args, **kwargs)
        self.fields['project'].empty_label = "Select a Project"
        self.fields['transaction_type'].choices = [("", "Select Transaction Type")] + list(self.fields['transaction_type'].choices)
        # Filter projects based on assigned projects for the user
        if self.user:
            assigned_projects = AssignedProject.objects.filter(user=self.user).values_list('project', flat=True)
            self.fields['project'].queryset = self.fields['project'].queryset.filter(id__in=assigned_projects)
         
         
            



class AssignProjectForm(forms.ModelForm):
    class Meta:
        model = AssignedProject
        fields = ['user', 'project', 'rate_of_interest', 'return_period']  # Include relevant fields
        widgets = {
            'rate_of_interest': forms.NumberInput(attrs={'placeholder': 'Enter interest rate'}),
            'return_period': forms.Select(attrs={'class': 'form-select'}),
        }
      
      



User = get_user_model()

class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone_number', 'address', 'country']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control  ',
              
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control  ',
              
            }),
            'username': forms.TextInput(attrs={
                'class': 'form-control  ',
              
            }),
            'email': forms.TextInput(attrs={
                'class': 'form-control  ',
              
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control  ',
              
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',  
                'rows': 1,  # Adjust the height
                'cols': 50,  # Optional, adjust width if necessary
                'style': 'resize: none;'  # Prevents resizing (optional)
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control  ',
              
            }),
        }
class PasswordEditForm(PasswordChangeForm):
    class Meta:
        fields = ['old_password', 'new_password1', 'new_password2']              
        


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
        validators=[validate_password]
    )
    reenter_password = forms.CharField(
        label="Re-enter New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        reenter_password = cleaned_data.get("reenter_password")

        if new_password and reenter_password and new_password != reenter_password:
            raise ValidationError("New passwords don't match!")
        return cleaned_data            
    

  


# class StaffTransactionForm(forms.ModelForm):
#     user = forms.ModelChoiceField(
#         queryset=CustomUser.objects.all(),
#         label="Select User"
#     )
#     project = forms.ModelChoiceField(
#         queryset=InvestmentProject.objects.filter(is_active=True),
#         label="Select Project"
#     )
#     transaction_date = forms.DateTimeField(
#         widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
#         label="Transaction Date"
#     )

#     class Meta:
#         model = Transaction
#         fields = ['user', 'project', 'amount', 'transaction_type', 
#                  'narration', 'receipt', 'transaction_date']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # No need for user-specific project filtering anymore



class StaffTransactionForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select User"  # This adds a default option as a placeholder
    )
    project = forms.ModelChoiceField(
        queryset=InvestmentProject.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Project"
    )
    transaction_type = forms.ChoiceField(
        choices=[('', 'Select Transaction Type')] + list(Transaction.TRANSACTION_TYPES),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    transaction_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        label="Transaction Date"
    )

    class Meta:
        model = Transaction
        fields = ['user', 'project', 'amount', 'transaction_type', 'narration', 'receipt', 'transaction_date']
        widgets = {
            'amount': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Transaction Amount'
            }),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'narration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Narration'
            }),
            'receipt': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            
        }

        
        


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = UserDocument
        fields = ['document_type', 'file', 'expiration_date']
        widgets = {
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
        }            