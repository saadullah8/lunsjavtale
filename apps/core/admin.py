from django.contrib import admin
from .models import (
    ValidArea, TypeOfAddress, Language, FAQCategory, FAQ, 
    SupportedBrand, Partner, FollowUs, Promotion, ContactUs, WhoUAre
)

@admin.register(ValidArea)
class ValidAreaAdmin(admin.ModelAdmin):
    list_display = ('post_code', 'name', 'is_active')
    search_fields = ('post_code', 'name')

@admin.register(TypeOfAddress)
class TypeOfAddressAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'is_active')
    list_filter = ('category', 'is_active')

@admin.register(SupportedBrand)
class SupportedBrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')

@admin.register(FollowUs)
class FollowUsAdmin(admin.ModelAdmin):
    list_display = ('title', 'link_type', 'is_active')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'is_active')

@admin.register(ContactUs)
class ContactUsAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'company_name', 'category', 'contact')
    search_fields = ('name', 'email', 'company_name', 'message')
    list_filter = ('category',)

@admin.register(WhoUAre)
class WhoUAreAdmin(admin.ModelAdmin):
    list_display = ('title', 'role', 'is_active')
