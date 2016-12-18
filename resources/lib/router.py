__author__ = 'thesebas'

import re
from urlparse import urlparse, parse_qs
import uritemplate


class Route(object):
    def __init__(self, router, name, **kwargs):
        self.router = router
        self.name = name
        self.path = kwargs["path"]
        self.callback = kwargs["callback"]
        self.template = kwargs["template"]

    def execute(self, path_parts):
        matched = re.match(self.path, path_parts.path)
        if matched:
            params = matched.groupdict()

            if path_parts.query:
                params.update(parse_qs(path_parts.query))

            self.callback(params, path_parts, self)


class Router(object):
    def __init__(self, **kwargs):

        self.host = kwargs["host"]
        self.routes = {}

    def route(self, name, path, template):
        def inner(func):
            self.routes[name] = Route(self, name, path=path, callback=func, template=template)
            return func

        return inner

    def make(self, name, params={}):
        try:
            route = self.routes[name]
            parts = urlparse(self.host)
            return uritemplate.expand("{proto}://{host}{+path}", dict(proto=parts.scheme, host=parts.netloc,
                                                                      path=route.template(params)))
        except KeyError:
            return None

    def run(self, path):
        parts = urlparse(path)
        for name, route in self.routes.iteritems():
            route.execute(parts)


def expander(template):
    def inner(params):
        return uritemplate.expand(template, params)

    return inner
