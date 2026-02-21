
# third party imports
import firebase_admin
from django.conf import settings
from firebase_admin import credentials
from pyfcm import FCMNotification as PYFCMNotification

cred = credentials.Certificate(settings.FIREBASE_CONFIG_PATH)
firebase_admin.initialize_app(cred)


class ExFCMNotification:

    def __init__(self, title, message, token, notification_type="", image=""):
        self.push_service = PYFCMNotification(api_key=settings.FCM_KEY)
        self.title = title
        self.message = message
        self.token = token
        self.notification_type = notification_type
        self.fcm_key = settings.FCM_KEY
        self.image = image

    def get_payload(self):
        data = {
            "type": self.notification_type,
            "details": self.message,
            "title": self.title,
            "message": self.message,
            "image": self.image,
            "sound": "default",
            "notificationId": 12345,
            "show_in_foreground": True,
            "priority": "high",
            # "actions": "com.flog",
            "color": "red",
            "autoCancel": "true",
            "channelId": "fcm_FirebaseNotifiction_default_channel",
            "largeIcon": "ic_launcher",
            "lights": True,
            "icon": "ic_notif",
        }
        return data

    def send_notification(self):
        data = self.get_payload()
        result = self.push_service.notify_single_device(registration_id=self.token, message_title=self.title,
                                                        message_body=self.message, data_message=data, sound='default')
        if not result.get('success'):
            print("Error", result)

    def send_bulk_notification(self, tokens):
        tokens = self.push_service.clean_registration_ids(tokens)
        if tokens:
            data = self.get_payload()
            result = self.push_service.notify_multiple_devices(registration_ids=tokens, message_title=self.title,
                                                               message_body=self.message, data_message=data,
                                                               sound='default')
            if not result.get('success'):
                print("Error", result)
