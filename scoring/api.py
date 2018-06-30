#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import datetime
import logging
import hashlib
import uuid
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler

import field
import scoring

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class ClientsInterestsRequest(field.FieldHolder):
    client_ids = field.ClientIDsField(required=True)
    date = field.DateField(required=False, nullable=True)

    def nclients(self):
        return len(self.client_ids)

    def validate(self):
        super().validate()
        if not self.client_ids:
            raise ValueError('empty client ids list')

    def get(self, ctx, store, method_request):
        self.validate()
        interests_dict = {}
        for client_id in self.client_ids:
            interests_dict[client_id] = scoring.get_interests(store, client_id)
        ctx['nclients'] = self.nclients()
        return interests_dict, OK


class OnlineScoreRequest(field.FieldHolder):
    first_name = field.CharField(required=False, nullable=True)
    last_name = field.CharField(required=False, nullable=True)
    email = field.EmailField(required=False, nullable=True)
    phone = field.PhoneField(required=False, nullable=True)
    birthday = field.BirthDayField(required=False, nullable=True)
    gender = field.GenderField(required=False, nullable=True)

    def has(self):
        has_dict = {}
        for field_name in self.field_dict:
            field_value = getattr(self, field_name)
            if field_value is not None:
                has_dict[field_name] = field_value
        return has_dict

    def validate(self):
        super().validate()
        no_phone_or_email = self.phone is None or self.email is None
        no_first_or_last_name = self.first_name is None or self.last_name is None
        no_gender_or_birthday = self.gender is None or self.birthday is None
        if no_phone_or_email and no_first_or_last_name and no_gender_or_birthday:
            msg = 'At least one of pairs must be set: '
            msg += '(phone, email), (first_name, last_name), (gender, birthday)'
            raise ValueError(msg)

    def get(self, ctx, store, method_request):
        self.validate()
        if method_request.is_admin():
            score = 42
        else:
            score = scoring.get_score(
                store,
                self.phone,
                self.email,
                birthday=self.birthday,
                gender=self.gender,
                first_name=self.first_name,
                last_name=self.last_name)
        ctx['has'] = self.has()
        return {'score': score}, OK


class MethodRequest(field.FieldHolder):
    account = field.CharField(required=False, nullable=True)
    login = field.CharField(required=True, nullable=True)
    token = field.CharField(required=True, nullable=True)
    arguments = field.ArgumentsField(required=True, nullable=True)
    method = field.CharField(required=True, nullable=False)

    REQUEST_ROUTER = {'online_score': OnlineScoreRequest, 'clients_interests': ClientsInterestsRequest}

    def is_admin(self):
        return self.login == ADMIN_LOGIN

    def validate(self):
        super().validate()
        if self.method not in MethodRequest.REQUEST_ROUTER:
            raise ValueError('Unknown method requested')


def check_auth(request):
    if request.is_admin():
        hash_str = '{:s}{:s}'.format(datetime.datetime.now().strftime("%Y%m%d%H"), ADMIN_SALT)
    else:
        hash_str = '{:s}{:s}{:s}'.format(request.account, request.login, SALT)
    digest = hashlib.sha512(hash_str.encode('utf-8')).hexdigest()
    if digest == request.token:
        return True
    return False


def method_handler(request, ctx, store):
    response, code = None, None
    method_request = MethodRequest(request['body'])
    try:
        method_request.validate()
        if check_auth(method_request):
            class_request = MethodRequest.REQUEST_ROUTER[method_request.method]
            instance_request = class_request(method_request.arguments)
            response, code = instance_request.get(ctx, store, method_request)
        else:
            response, code = "Invalid token", FORBIDDEN
    except ValueError as e:
        response, code = str(e), INVALID_REQUEST
    return response, code


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        data_string = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
