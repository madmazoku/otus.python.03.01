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

METHOD_ROUTER = {}


class ClientsInterestsRequest(field.FieldHolder):
    client_ids = field.ClientIDsField(required=True)
    date = field.DateField(required=False, nullable=True)

    @property
    def nclients(self):
        return len(self.client_ids)

    def validate(self):
        error_msg = super().validate()
        if not error_msg and isinstance(self.client_ids, list) and not self.client_ids:
            error_msg.append('empty client list')
        return error_msg


class OnlineScoreRequest(field.FieldHolder):
    first_name = field.CharField(required=False, nullable=True)
    last_name = field.CharField(required=False, nullable=True)
    email = field.EmailField(required=False, nullable=True)
    phone = field.PhoneField(required=False, nullable=True)
    birthday = field.BirthDayField(required=False, nullable=True)
    gender = field.GenderField(required=False, nullable=True)

    @property
    def has(self):
        if not hasattr(self, '_has'):
            has_dict = {}
            for field_name in self.field_dict:
                field_value = getattr(self, field_name)
                if field_value is not None:
                    has_dict[field_name] = field_value
            self._has = has_dict
        return self._has

    def validate(self):
        error_msg = super().validate()
        if not error_msg and (self.phone is None or self.email is None) and (
                self.first_name is None or self.last_name is None) and (self.gender is None or self.birthday is None):
            error_msg.append('not enough arguments')
        return error_msg


class MethodRequest(field.FieldHolder):
    account = field.CharField(required=False, nullable=True)
    login = field.CharField(required=True, nullable=True)
    token = field.CharField(required=True, nullable=True)
    arguments = field.ArgumentsField(required=True, nullable=True)
    method = field.CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        hash_str = '{:s}{:s}'.format(datetime.datetime.now().strftime("%Y%m%d%H"), ADMIN_SALT)
    else:
        hash_str = '{:s}{:s}{:s}'.format(request.account, request.login, SALT)
    digest = hashlib.sha512(hash_str.encode('utf-8')).hexdigest()
    if digest == request.token:
        return True
    return False


def get_score(ctx, store, method_request, online_score_request):
    if method_request.is_admin:
        score = 42
    else:
        score = scoring.get_score(
            store,
            online_score_request.phone,
            online_score_request.email,
            birthday=online_score_request.birthday,
            gender=online_score_request.gender,
            first_name=online_score_request.first_name,
            last_name=online_score_request.last_name)
    ctx['has'] = online_score_request.has
    return {'score': score}


def get_interests(ctx, store, method_request, clients_interests_request):
    interests_dict = {}
    for client_id in clients_interests_request.client_ids:
        interests_dict[client_id] = scoring.get_interests(store, client_id)
        ctx['nclients'] = clients_interests_request.nclients
    return interests_dict


METHOD_ROUTER['online_score'] = {
    'object': OnlineScoreRequest,
    'action': get_score,
}
METHOD_ROUTER['clients_interests'] = {'object': ClientsInterestsRequest, 'action': get_interests}


def method_handler(request, ctx, store):
    response, code = None, INVALID_REQUEST
    method_request = MethodRequest(request['body'])
    error_msg = method_request.validate()
    if not error_msg:
        if not check_auth(method_request):
            code = FORBIDDEN
        elif method_request.method in METHOD_ROUTER:
            method = METHOD_ROUTER[method_request.method]
            object_request = method['object'](method_request.arguments)
            error_msg.extend(object_request.validate())
            if not error_msg:
                response = method['action'](ctx, store, method_request, object_request)
                code = OK
    if error_msg:
        response = '; '.join(error_msg)
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
