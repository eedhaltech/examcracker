from django import forms

from .models import ContactMessage, BlogComment


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ("name", "email", "subject", "message")
        widgets = {
            "name": forms.TextInput(attrs={"class": "panel-input"}),
            "email": forms.EmailInput(attrs={"class": "panel-input"}),
            "subject": forms.TextInput(attrs={"class": "panel-input"}),
            "message": forms.Textarea(attrs={"class": "panel-input", "rows": 6}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(attrs={"class": "panel-input", "rows": 4, "placeholder": "Write your comment…"}),
        }

