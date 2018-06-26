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
        return instance.__dict__.get(self.field_name + '_converted', instance.__dict__.get(self.field_name, None))

    def __set__(self, instance, value):
        instance.__dict__[self.field_name] = value
        instance.__dict__.pop(self.field_name + '_converted', 'None')

    def format_err(self, msg):
        return '{:s}: {:s}'.format(self.field_name, msg)

    def validate(self, instance):
        error_msgs = []
        if self.required and self.field_name not in instance.__dict__:
            error_msgs.append(self.format_err('required field absent'))
        if not self.nullable and getattr(instance, self.field_name) is None:
            error_msgs.append(self.format_err('field must not be null'))
        return error_msgs


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
    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if not isinstance(value, str):
            error_msgs.append(self.format_err('field must be string'))
        return error_msgs


class ArgumentsField(Field):
    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if not isinstance(value, dict):
            error_msgs.append(self.format_err('field must be object'))
        return error_msgs


VALIDATE_EMAIL_RE = re.compile("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$")


class EmailField(CharField):
    @staticmethod
    def is_valid_email(email):
        return len(email) > 7 and re.match(VALIDATE_EMAIL_RE, email) is not None

    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if isinstance(value, str) and not self.is_valid_email(value):
            error_msgs.append(self.format_err('field must be valid email address'))
        return error_msgs


VALIDATE_PHONE_RE = re.compile("^7\\d+$")


class PhoneField(Field):
    @staticmethod
    def is_valid_phone(phone):
        return len(phone) == 11 and re.match(VALIDATE_PHONE_RE, phone) is not None

    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if not (isinstance(value, str) or isinstance(value, int)):
            error_msgs.append(self.format_err('field must be string or number'))
        else:
            if isinstance(value, int):
                value = str(value)
                instance.__dict__[self.field_name + '_converted'] = value
            if not self.is_valid_phone(value):
                error_msgs.append(self.format_err('field must be valid phone (11 digits, leading digit = 7)'))
        return error_msgs


DATE_FIELD_FORMAT = "%d.%m.%Y"


class DateField(CharField):
    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if isinstance(value, str):
            try:
                value = datetime.datetime.strptime(value, DATE_FIELD_FORMAT).date()
                instance.__dict__[self.field_name + '_converted'] = value
            except ValueError as e:
                error_msgs.append(self.format_err('invalid date format ({!s})'.format(e)))
        return error_msgs


class BirthDayField(DateField):
    @staticmethod
    def is_valid_birthday(date):
        td = datetime.date.today()
        years = td.year - date.year
        if td.month < date.month or (td.month == date.month and td.day < date.day):
            years -= 1
        return years <= 70

    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if isinstance(value, datetime.date) and not self.is_valid_birthday(value):
            error_msgs.append(self.format_err('invalid birthday'))
        return error_msgs


class GenderField(Field):
    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if not isinstance(value, int):
            error_msgs.append(self.format_err('field must be number'))
        elif value not in [0, 1, 2]:
            error_msgs.append(self.format_err('field must be 0, 1 or 2'))
        return error_msgs


class ClientIDsField(Field):
    def validate(self, instance):
        error_msgs = super().validate(instance)
        value = getattr(instance, self.field_name)
        if value is None:
            return error_msgs
        if not isinstance(value, list):
            error_msgs.append(self.format_err('field must be list'))
        elif not all(isinstance(x, int) for x in value):
            error_msgs.append(self.format_err('field must be list of numbers'))
        return error_msgs
