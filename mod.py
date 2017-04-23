from flask import Blueprint, abort, jsonify, render_template, request
from decorators import mod_required, api_disallowed
from models import User
from sqlalchemy import func
import json

mod = Blueprint('mod', __name__, template_folder='templates')


@mod.route('/settings')
@mod_required
def settings():
    # shows site settings
    return render_template("settings.html")


@mod.route('/users')
@mod_required
@api_disallowed
def users():
    # manage users
    page = int(request.args.get('page', 1))
    count = int(request.args.get('limit', 25))
    None if page == 1 else page - 1
    if page == 1:
        button_back = False
    else:
        button_back = f"/mod/users?page={page-1}&limit={count}"
    button_next = f"/mod/users?page={page+1}&limit={count}"
    if request.args.get('user') is not None:
        username = request.args.get('user')
        users = User.query.filter(
            func.lower(
                User.username) == func.lower(username)).first()
        return render_template("users.html", users=[users])
    elif request.args.get('mod') is not None:
        raw = str(request.args.get('mod')).lower()
        if raw == "false":
            mod = False
        else:
            mod = True
        users = User.query.filter_by(
            form_mod=mod).paginate(
            page, count, False).items
        if button_back:
            button_back += f"&mod={raw}"
        button_next += f"&mod={raw}"
    elif request.args.get('exempt') is not None:
        raw = str(request.args.get('exempt')).lower()
        if raw == "false":
            exempt = False
        else:
            exempt = True
        users = User.query.filter_by(
            is_exempt=exempt).paginate(
            page, count, False).items
        if button_back:
            button_back += f"&exempt={raw}"
        button_next += f"&exempt={raw}"
    else:
        users = User.query.paginate(page, count, False).items
    button_data = [button_back, button_next]
    return render_template("users.html", users=users, button_data=button_data)


@mod.route('/user/<string:username>')
@mod_required
@api_disallowed
def user_lookup(username):
    # shows a user's page
    is_json = False
    if username.endswith(".json"):
        username = username.split(".")[0]
        is_json = True

    user = User.query.filter_by(username=username).first()
    if not user:
        # check to see if a similar username exists
        user = User.query.filter(User.username.ilike(username)).first()
        show_warning = True
    if user.username.lower() == username.lower():
        show_warning = False
    if not user:
        return abort(404)
    if is_json:
        return jsonify(username=user.username,
                       response_md=user.full_body_md,
                       response_html=user.full_body_html,
                       submitted=user.submitted,
                       processed=user.processed,
                       last_login=user.last_login)
    return render_template(
        "user.html",
        user=user,
        username=username,
        show_warning=show_warning)


@mod.route('/questions')
@mod_required
def questions():
    return render_template("question_editor.html")


@mod.route('/response')
@mod_required
def response():
    return render_template("response_editor.html")


@mod.route('/api')
@mod_required
def api():
    with open("data/api_docs.json") as api_docs:
        data = json.loads(api_docs.read())
    return render_template("api.html", data=data)
