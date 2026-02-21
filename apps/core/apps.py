from django.apps import AppConfig, apps
from django.contrib import admin


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'

    def ready(self):
        for config in apps.get_app_configs():
            admin_module = getattr(config.module, 'admin', None)
            for model in config.get_models():
                if not admin.sites.site.is_registered(model):
                    modeladmin = getattr(admin_module, f'{model.__name__}ModelAdmin', None)
                    admin.sites.site.register(model, modeladmin)
