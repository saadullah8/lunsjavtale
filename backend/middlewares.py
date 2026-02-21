from django.utils import timezone

from .authentication import Authentication

x = []


def get_key(data):
    if data.prev:
        return get_key(data.prev)
    return data.key


class W3AuthMiddleware(object):
    """Custom Auth Middlewares"""
    def resolve(self, next, root, info, **kwargs):
        if root is None:
            info.context.user = self.authorize_user(info)
        return next(root, info, **kwargs)

    @staticmethod
    def authorize_user(info):
        auth = Authentication(info.context)
        return auth.authenticate()


class W3AuthMiddlewareF(object):
    """Custom Auth Middlewares"""

    def __init__(self, **kwargs):
        self.q_start = False
        self.q_start_time = None
        self.qr = {}

    def resolve(self, next, root, info, **kwargs):
        print(info)
        if not self.q_start:
            self.q_start_time = timezone.now()
            self.q_start = True
        end_time = timezone.now()
        dur = end_time - self.q_start_time
        # print(dur.microseconds / 1000)
        # print(end_time, self.q_start_time)
        # print("dur", dur.microseconds)
        # print(info.path.prev)
        if info.path:
            key = get_key(info.path)
            self.qr[key] = dur.microseconds / 1000
            # else:
            #     self.qr[key] += dur.microseconds / 1000
        print(self.qr)
        return next(root, info, **kwargs)

    @staticmethod
    def authorize_user(info):
        auth = Authentication(info.context)
        return auth.authenticate()
