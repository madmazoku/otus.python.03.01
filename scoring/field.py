#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import datetime


class FieldError(Exception):
    def __init__(self, field_name, error_msg):
        self.field_name = field_name or 'unknown'
        self.error_msg = error_msg or 'unknown'

    def __str__(self):
        return '{:s}: {:s}'.format(self.field_name, self.error_msg)


class FieldHolderError(Exception):
    def __init__(self, error_msg):
        self.error_msg = error_msg or 'unknown'

    def __str__(self):
        return self.error_msg


class Field(object):
    def __init__(self, required=False, nullable=False):
        self.field_name = None
        self.required = required
        self.nullable = nullable

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.field_name, None)

    def __set__(self, instance, value):
        (data, success) = self.convert(value)
        if success and self.validate(data):
            instance.__dict__[self.field_name] = data
        else:
            raise FieldError(self.field_name, 'invalid')

    def convert(self, value):
        return (value, True)

    def validate(self, value):
        return value is not None or self.nullable


class FieldHolderMeta(type):
    def __new__(cls, name, bases, attrs):
        attrs['field_dict'] = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Field):
                attr_value.field_name = attr_name
                attrs['field_dict'][attr_name] = attr_value
        return super().__new__(cls, name, bases, attrs)


class FieldHolderBase(object):
    def __init__(self, struct):
        for field_name, field_value in self.field_dict.items():
            if field_value.required and field_name not in struct:
                raise FieldError(field_name, 'required')
            else:
                setattr(self, field_name, struct.get(field_name, None))
        (success, error_msg) = self.validate()
        if not success:
            raise FieldHolderError(error_msg)

    def validate(self):
        return (True, None)

    def dump_fields(self):
        for field_name in self.field_dict:
            print("{!s}: {!s} ({!s})".format(field_name, getattr(self, field_name), type(getattr(self, field_name))))


class CharField(Field):
    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, str))


class ArgumentsField(Field):
    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, dict))


VALIDATE_EMAIL_RE = re.compile("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$")


class EmailField(CharField):
    @staticmethod
    def is_valid_email(email):
        return len(email) > 7 and re.match(VALIDATE_EMAIL_RE, email) is not None

    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, str) and self.is_valid_email(value))


VALIDATE_PHONE_RE = re.compile("^7\\d+$")


class PhoneField(Field):
    @staticmethod
    def is_valid_phone(phone):
        return len(phone) == 11 and re.match(VALIDATE_PHONE_RE, phone) is not None

    def convert(self, value):
        data = None
        success = True
        if value is not None:
            data = str(value)
            success = self.is_valid_phone(data)
        return (data, success)


class DateField(Field):
    def convert(self, value):
        date = None
        success = False
        try:
            if value is not None:
                date = datetime.datetime.strptime(value, "%d.%m.%Y").date()
            success = True
        except ValueError:
            pass
        return date, success


class BirthDayField(DateField):
    @staticmethod
    def is_valid_birthday(date):
        td = datetime.date.today()
        years = td.year - date.year
        if td.month < date.month or (td.month == date.month and td.day < date.day):
            years -= 1
        return years <= 70

    def validate(self, value):
        return super().validate(value) and (value is None or self.is_valid_birthday(value))


class GenderField(Field):
    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, int) and value in [0, 1, 2])


class ClientIDsField(Field):
    @staticmethod
    def is_number_list(lst):
        if not isinstance(lst, list):
            return False
        for x in lst:
            if not isinstance(x, int) or x < 0:
                return False
        return True

    def validate(self, value):
        return super().validate(value) and (value is None or self.is_number_list(value))


class FieldHolder(FieldHolderBase, metaclass=FieldHolderMeta):
    pass


if __name__ == '__main__':

    class Struct(FieldHolder):
        char = CharField()
        arguments = ArgumentsField()
        email = EmailField()
        phone = PhoneField()
        date = DateField()
        birthday = BirthDayField()
        gender = GenderField()
        client_ids = ClientIDsField()

    s = {
        "char": "123", "arguments": {"a": 1, "b": 2, "c": 3}, "email": "aaa@gmail.com", "phone": "71234567890", "date":
        "20.07.2017", "birthday": "20.07.1917", "gender": 1, "client_ids": [1, 2, 3, 4, 5, 1]
    }

    st = Struct(s)

    st.dump_fields()
