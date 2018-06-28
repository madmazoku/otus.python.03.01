#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import datetime


class Field(object):
    def __init__(self, required=False, nullable=False):
        self.field_name = None
        self.required = required
        self.nullable = nullable

    def __get__(self, instance, owner):
        return instance.__dict__[self.field_name]

    def __set__(self, instance, value):
        instance.__dict__[self.field_name + '_orig'] = value
        instance.__dict__.pop(self.field_name, 'None')

    def format_err(self, msg):
        return '{:s}: {:s}'.format(self.field_name, msg)

    def validate(self, instance):
        error_msgs = []
        value = None
        if self.field_name + '_orig' in instance.__dict__:
            value = instance.__dict__[self.field_name + '_orig']
        elif self.required:
            error_msgs.append(self.format_err('required field absent'))
        if value is not None:
            value_converted = self.validate_convert_value(error_msgs, instance, value)
            if not error_msgs:
                instance.__dict__[self.field_name] = value_converted
        elif not self.nullable:
            error_msgs.append(self.format_err('field must not be null'))
        else:
            instance.__dict__[self.field_name] = None
        return error_msgs

    def validate_convert_value(self, error_msgs, instance, value):
        return value


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
            if field_name in struct:
                setattr(self, field_name, struct[field_name])

    def validate(self):
        error_msgs = []
        for field_name, field_value in self.field_dict.items():
            error_msgs.extend(field_value.validate(self))
        return error_msgs

    def dump_fields(self):
        for field_name in self.field_dict:
            print("{!s}: {!s} ({!s})".format(field_name, getattr(self, field_name), type(getattr(self, field_name))))


class FieldHolder(FieldHolderBase, metaclass=FieldHolderMeta):
    pass


class CharField(Field):
    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs and not isinstance(value, str):
            error_msgs.append(self.format_err('field must be string'))
        return value


class ArgumentsField(Field):
    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs and not isinstance(value, dict):
            error_msgs.append(self.format_err('field must be object'))
        return value


class EmailField(CharField):
    VALIDATE_EMAIL_RE = re.compile("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$")

    @staticmethod
    def is_valid_email(email):
        return len(email) > 7 and re.match(EmailField.VALIDATE_EMAIL_RE, email) is not None

    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs and not EmailField.is_valid_email(value):
            error_msgs.append(self.format_err('field must be valid email address'))
        return value


class PhoneField(Field):
    VALIDATE_PHONE_RE = re.compile("^7\\d+$")

    @staticmethod
    def is_valid_phone(phone):
        return len(phone) == 11 and re.match(PhoneField.VALIDATE_PHONE_RE, phone) is not None

    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs:
            if not isinstance(value, str) and not isinstance(value, int):
                error_msgs.append(self.format_err('field must be string or number'))
            else:
                if isinstance(value, int):
                    value = str(value)
                if not PhoneField.is_valid_phone(value):
                    error_msgs.append(self.format_err('field must be valid phone (11 digits, leading digit = 7)'))
        return value


class DateField(CharField):
    DATE_FIELD_FORMAT = "%d.%m.%Y"

    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs:
            try:
                value = datetime.datetime.strptime(value, DateField.DATE_FIELD_FORMAT).date()
            except ValueError as e:
                error_msgs.append(self.format_err('invalid date format ({!s})'.format(e)))
        return value


class BirthDayField(DateField):
    @staticmethod
    def is_valid_birthday(date):
        td = datetime.date.today()
        years = td.year - date.year
        if td.month < date.month or (td.month == date.month and td.day < date.day):
            years -= 1
        return years <= 70

    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs and not BirthDayField.is_valid_birthday(value):
            error_msgs.append(self.format_err('invalid birthday'))
        return value


class GenderField(Field):
    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs:
            if not isinstance(value, int):
                error_msgs.append(self.format_err('field must be number'))
            elif value not in [0, 1, 2]:
                error_msgs.append(self.format_err('field must be 0, 1 or 2'))
        return value


class ClientIDsField(Field):
    def validate_convert_value(self, error_msgs, instance, value):
        value = super().validate_convert_value(error_msgs, instance, value)
        if not error_msgs:
            if not isinstance(value, list):
                error_msgs.append(self.format_err('field must be list'))
            elif not all(isinstance(x, int) for x in value):
                error_msgs.append(self.format_err('field must be list of numbers'))
        return value
