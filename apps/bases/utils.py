
import json
import random
import re
import string
import uuid
from math import atan2, cos, radians, sin, sqrt
from typing import Type

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers import json as s_json
from django.forms import model_to_dict
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from graphql import GraphQLError

from apps.bases.constant import ignorable_field_types


def build_absolute_uri(path, host) -> str:
    """
        Find absolute url of a path by including site-url
    """
    url = f"http://{host}/{path}" if re.findall("127.0.0.1", str(host)) else f"https://{host}/{path}"
    return url


def set_absolute_uri(path) -> str:
    """
    """
    site = settings.SITE_URL
    url = f"{site}/{path}"
    return url


def get_json_data(serializers_data) -> object:
    """
        find json-data from a serialized-data and return
    """
    data = json.dumps(serializers_data)
    data = json.loads(data)
    return data


def get_serialized_data(qs, fields: list = []) -> object:
    """
        find json-data from a serialized-data and return
    """
    serializer = s_json.Serializer()
    if fields:
        data = serializer.serialize(qs, fields=fields)
    else:
        data = serializer.serialize(qs)
    return json.loads(data)


def get_headers(request) -> object:
    """
    """
    try:
        data = {i[0]: i[1] for i in request.META.items() if i[0].startswith('HTTP_')}
    except BaseException:
        data = None
    return data


def create_token() -> str:
    """
        get an uuid string and return
    """
    return uuid.uuid4()


def create_password(size=8, chars=string.ascii_letters + string.digits):
    """
    """
    return ''.join(random.choice(chars) for _ in range(size))


def email_validator(email):
    """
        Validate an email with a default expression format
        and raise error if not matched
    """
    regex = r"^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$"
    if not (re.search(regex, email)):
        raise ValidationError(_("Email address format is not valid."))


def email_checker(email):
    """
        Validate an email with a default expression format
        and return true/false
    """
    regex = r"^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$"
    if (re.search(regex, email)):
        return True
    return False


def username_validator(value):
    """
        Validate a username with a default expression format
        and raise error if not matched.
        The username consists of 6 to 30 characters inclusive.
        If the username consists of less than 6 or greater than 30 characters,
        then it is an invalid username.
        The username can only contain alphanumeric characters and underscores (_).
        Alphanumeric characters describe the character set consisting of lowercase characters [a – z],
        uppercase characters [A – Z], and digits [0 – 9].
        The first character of the username must be an alphabetic character,
        i.e., either lowercase character [a – z] or uppercase character [A – Z].
    """
    length = len(value)
    regex = r'[\w]+$'
    if not (re.search(regex, value)):
        raise ValidationError(_("username should be alphanumeric, may include underscore."))
    elif length < 5 or length > 30:
        raise ValidationError(_("username length should not less than 5 and greater than 30 characters."))


def coupon_validator(value):
    """
        Validate a username with a default expression format
        and raise error if not matched.
        The username consists of 6 to 30 characters inclusive.
        If the username consists of less than 6 or greater than 30 characters,
        then it is an invalid username.
        The username can only contain alphanumeric characters and underscores (_), hyphen(-).
        Alphanumeric characters describe the character set consisting of
        uppercase characters [A – Z], and digits [0 – 9].
        The first character of the username must be an alphabetic character,
        i.e., either lowercase character [a – z] or uppercase character [A – Z].
    """
    length = len(value)
    regex = r'^[A-Z][A-Z0-9_-]+$'
    if not (re.search(regex, value)):
        raise ValidationError(_(
            "promo-code should be uppercase and alphanumeric, may include underscore, hyphen and start with a letter."))
    elif length < 6 or length > 100:
        raise ValidationError(_("promo-code length should not less than 6 and greater than 100 characters."))


def random_string_generator(size=8, chars=string.ascii_lowercase + string.digits):
    """
        generate a random-string of a default size containing lowercase-characters
    """
    return ''.join(random.choice(chars) for _ in range(size))


def unique_slug_generator(instance, new_slug=None):
    """
        Generate a unique string with a slug field and a title character (char) field.
    """

    if new_slug is not None:
        slug = new_slug
    else:
        slug = slugify(instance.name, allow_unicode=True)
    Klass = instance.__class__
    qs_exists = Klass.objects.filter(slug=slug).exclude(id=instance.id).exists()
    if qs_exists:
        if not slug:
            new_slug = "category-{randstr}".format(
                randstr=random_string_generator(size=4)
            )
        else:
            new_slug = "{slug}-{randstr}".format(
                slug=slug,
                randstr=random_string_generator(size=4))
        return unique_slug_generator(instance, new_slug=new_slug)

    return slug


def advertise_unique_slug_generator(instance, new_slug=None):
    """
        Generate a unique string with a slug field and a title character (char) field.
    """

    if new_slug is not None:
        slug = new_slug
    else:
        if instance.slug:
            slug = instance.slug
        else:
            slug = slugify(instance.title, allow_unicode=True)
    Klass = instance.__class__
    qs_exists = Klass.objects.filter(slug=slug).exclude(id=instance.id).exists()
    if qs_exists:
        if not slug:
            new_slug = "advertisement-{randstr}".format(
                randstr=random_string_generator(size=6)
            )
        else:
            new_slug = "{slug}-{randstr}".format(
                slug=slug,
                randstr=random_string_generator(size=4))
        return advertise_unique_slug_generator(instance, new_slug=new_slug)

    return slug


def get_file_contents(file):
    """
        Read a file content
    """
    f = open(file, 'r')
    file_content = f.read()
    f.close()
    return file_content


def camel_case_format(word: str):
    """
        Transform a string from snake_case format to camelCase
    """
    f_word = str(word).split("_")
    return f_word[0] + "".join(w.capitalize() for w in f_word[1:])


def find_grand_parent(category):
    """
        find the top parent of any category-object
    """
    parent = category.parent
    if parent and parent.parent:
        return find_grand_parent(parent)
    elif parent and parent.parent is None:
        return parent
    return None


def find_grand_parent_list(category, parent_list=None):
    """
        find all-level parents of any category-object
        and return id-list of those
    """
    parent_list = parent_list if parent_list else []
    try:
        parent = category.parent
        if parent and parent.parent:
            parent_list.append(parent.id)
            return find_grand_parent_list(parent, parent_list)
        elif parent and parent.parent is None:
            parent_list.append(parent.id)
            return parent_list
        return parent_list
    except Exception:
        return parent_list


def get_model_fields(model):
    """
        Get all the fields related to a model
    """
    return model._meta.get_fields()


def get_absolute_path(info, file):
    """
        Get all the fields related to a model
    """
    file_path = None
    if file and str(file.url).startswith('http'):
        file_path = file.url
    elif file and not str(file.url).startswith('http'):
        host = info.context.headers.get('host')
        file_path = f"http://{host}{file.url}" if re.findall("localhost", str(host)) else f"https://{host}{file.url}"
    return file_path


def get_object_dict(obj: object, fields: list = None) -> dict:
    """
        Transform an object to a dict including changes in some field-format to string
        for some default fields
    """
    if fields:
        dict_data = model_to_dict(obj, fields=fields)
    else:
        dict_data = model_to_dict(obj)
    for atr in dict_data:
        if type(dict_data[atr]) not in ignorable_field_types:
            dict_data[atr] = str(dict_data[atr])
    return dict_data


def get_object_dict_excludes(obj: object, excludes: list):
    """
        Transform an object to a dict including changes in some field-format to string
        excluding some fields
    """
    dict_data = model_to_dict(obj, exclude=excludes)
    for atr in dict_data:
        if type(dict_data[atr]) not in ignorable_field_types:
            dict_data[atr] = str(dict_data[atr])
    return dict_data


def raise_graphql_error(message: str, code="invalid_request", field_name=None):
    """
        Raise graphql error by message and code
    """
    extensions = {'code': code}
    if field_name:
        extensions['errors'] = {field_name: message}
    else:
        extensions['message'] = message
    raise GraphQLError(
        message=message,
        extensions=extensions
    )


def raise_graphql_error_with_fields(message, errors: dict, code="invalid_request"):
    """
        Raise graphql error by message, code and list of errors
    """
    raise GraphQLError(
        message=message,
        extensions={
            'errors': errors,
            'code': code
        }
    )


def get_object_by_id(model, object_id, issue="id"):
    """
        Getting an object from a model by some default attributes.
        bases are those attributes which can be referred for issue arise.
    """
    try:
        obj = model.objects.get(id=object_id)
        return obj
    except Exception:
        raise GraphQLError(
            message=f"{model.__name__} matching query does not exist.",
            extensions={
                "errors": {issue: f"Select a valid choice. '{object_id}' is not one of the available choices."},
                "code": "invalid_request"
            }
        )


def get_object_by_attrs(model, attrs_with_value: dict, base: dict):
    """
        Getting an object from a model by some default attributes.
        base will hold attribute which can be referred for issue arise.
    """
    try:
        obj = model.objects.get(**attrs_with_value)
        return obj
    except Exception:
        raise GraphQLError(
            message=f"{model.__name__} matching query does not exist.",
            extensions={
                "errors": {
                    base.get('name'): f"Select a valid choice. '{base.get('value')}' is not one of the available choices."},
                "code": "invalid_request"
            }
        )


def calculate_distance(x, y):
    """Function to compute the distance between two points x, y"""

    # distance = gmaps_distance_calculation(x[0], x[1], y[0], y[1])
    distance = None
    if not distance:
        R = 6373.0
        lat1 = radians(x[0])
        lon1 = radians(x[1])
        lat2 = radians(y[0])
        lon2 = radians(y[1])

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

    return distance * 1000


def create_graphql_error(form):
    error_data = {
        camel_case_format(error): err
        for error in form.errors
        for err in form.errors[error]
    }
    raise GraphQLError(
        message="Invalid input request.",
        extensions={"errors": error_data, "code": "invalid_input"},
    )


def get_object_by_kwargs(model, kwargs: dict):
    try:
        obj = model.objects.get(**kwargs)
        return obj
    except model.DoesNotExist:
        raise GraphQLError(
            message=f"{model.__name__} matching query does not exist.",
            extensions={
                "errors": {
                    field: f"No instance was found associated with '{value}'"
                    for field, value in kwargs.items()
                },
                "code": "invalid_request",
            },
        )


def get_object_or_none(
    model: Type,
    id: str = None,
    default_value: Type = None,
    check_delete: bool = False,
    extra_fields: dict = {},
):
    """if id is given and object is not found then raise GraphqlError else return None"""
    if id:
        if extra_fields:
            extra_fields["id"] = id
            obj = get_object_by_kwargs(model, extra_fields)
        else:
            obj = get_object_by_id(model, id)
        if check_delete and obj.is_deleted:
            raise GraphQLError(
                message="Can not do operations on already deleted object.",
                extensions={
                    "errors": {
                        "message": "Can not do operations on already deleted object."
                    }
                },
            )
        return obj

    return default_value
