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

    @property
    def nclients(self):
        return len(self.client_ids)

    def validate(self):
        error_msg = super().validate()
        if self.client_ids is not None and isinstance(self.client_ids, list) and len(self.client_ids) == 0:
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
        if self.phone is not None and self.email is not None:
            return error_msg
        if self.first_name is not None and self.last_name is not None:
            return error_msg
        if self.gender is not None and self.birthday is not None:
            return error_msg
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


def get_score(ctx, store, mr, osr):
    if mr.is_admin:
        score = 42
    else:
        score = scoring.get_score(
            store,
            osr.phone,
            osr.email,
            birthday=osr.birthday,
            gender=osr.gender,
            first_name=osr.first_name,
            last_name=osr.last_name)
    ctx['has'] = osr.has
    return {'score': score}


def get_interests(ctx, store, mr, cir):
    cir = ClientsInterestsRequest(mr.arguments)
    interests_dict = {}
    for client_id in cir.client_ids:
        interests_dict[client_id] = scoring.get_interests(store, client_id)
        ctx['nclients'] = cir.nclients
    return interests_dict


method_router = {
    'online_score': {
        'object': OnlineScoreRequest,
        'action': get_score,
    },
    'clients_interests': {
        'object': ClientsInterestsRequest,
        'action': get_interests
    }
}


def method_handler(request, ctx, store):
    response, code = None, INVALID_REQUEST
    mr = MethodRequest(request['body'])
    error_msg = mr.validate()
    if len(error_msg) > 0:
        response = '; '.join(error_msg)
    elif not check_auth(mr):
        code = FORBIDDEN
    elif mr.method in method_router:
        obj = method_router[mr.method]['object'](mr.arguments)
        error_msg = obj.validate()
        if len(error_msg) > 0:
            response = '; '.join(error_msg)
        else:
            response = method_router[mr.method]['action'](ctx, store, mr, obj)
            code = OK
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
