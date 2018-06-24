import re
import datetime


class Field(object):
    def __init__(self, required=False, nullable=False):
        self.field_name = None
        self.required = required
        self.nullable = nullable

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.field_name, None)

    def __set__(self, instance, value):
        if self.validate(value):
            instance.__dict__[self.field_name] = value
        else:
            raise ValueError

    def validate(self, value):
        return value is not None or self.nullable


class FieldHolderMeta(type):
    def __new__(cls, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, Field):
                attr_value.field_name = attr_name
                attrs['field_dict'][attr_name] = attr_value
        return super().__new__(cls, name, bases, attrs)


class FieldHolderBase(object):
    field_dict = {}

    def __init__(self, struct):
        for field_name, field_value in self.field_dict.items():
            if field_value.required and field_name not in struct:
                raise ValueError
            else:
                setattr(self, field_name, struct.get(field_name, None))

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


VALIDATE_PHONE_RE = re.compile("^\\d+$")


class PhoneField(Field):
    @staticmethod
    def is_valid_phone(phone):
        return len(phone) == 11 and re.match(VALIDATE_PHONE_RE, phone) is not None

    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, str) and self.is_valid_phone(value))


class DateField(Field):
    def __set__(self, instance, value):
        if self.validate(value):
            date = None
            if value is not None:
                date = datetime.datetime.strptime(value, "%d.%m.%Y").date()
            instance.__dict__[self.field_name] = date
        else:
            raise ValueError

    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, str))


class BirthDayField(DateField):
    pass


class GenderField(Field):
    def validate(self, value):
        return super().validate(value) and (value is None or isinstance(value, int) and value >= 0)


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
