from functools import wraps
from flask import g, url_for, redirect, abort, request


def login_required(f):
    # requires users to be logged in to view
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            dest = f.__name__
            if '/mod/' in request.path:
                dest = "mod." + dest
            elif '/api/' in request.path:
                dest = "api." + dest
            return redirect(url_for('auth', next=dest))
        return f(*args, **kwargs)
    return decorated_function


def mod_required(f):
    # requires user to be a moderator to view
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            dest = f.__name__
            if '/mod/' in request.path:
                dest = "mod." + dest
            elif '/api/' in request.path:
                dest = "api." + dest
            return redirect(url_for('auth', next=dest))
        if not g.user.form_mod:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


def api_disallowed(f):
    # requires that logins be browser-based to access
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.api_login:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function
