from flask import Blueprint, g, jsonify, redirect, request, Response
from utils import age_to_words, bad_request
from decorators import mod_required, api_disallowed
from reddit import send_message, route
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, inspect
from models import User
from models import db
from werkzeug.exceptions import HTTPException
import random
import json
import string

api = Blueprint('api', __name__, template_folder='templates')


@api.route('/questions', methods=['POST'])
@mod_required
def questions():
    # updates the question template data

    # validating and loading question data
    # valid structure looks like this:
    # https://gist.github.com/Jakeable/60ebdae1a8fe3918fee3be1f8efa9ee5
    dirty_data = request.get_json(force=True)
    sanitized = []
    max_num = None
    ids = 0
    for d in dirty_data:
        out = {}
        out_ids = 1
        out["text"] = d["text"]

        # type validation
        if d["type"].lower() not in [
            "text",
            "textarea",
            "number",
            "radio",
            "checkbox",
                "dropdown"]:
            continue
        else:
            out["type"] = d["type"].lower()

        # set priority
        if "priority" in d.keys():
            out["priority"] = d["priority"]
            if not max_num or max_num > out["priority"]:
                max_num = out["priority"]
        else:
            out["priority"] = None

        # add choices/data
        if "data" in d.keys() and d["type"] in [
                "radio", "checkbox", "dropdown"]:
            out_data = []
            for item in d["data"]:
                out_data.append(str(item))
            if len(out_data) > 0:
                out["data"] = out_data
                out_ids += len(out_data)

        # add validators
        if "validators" in d.keys() and len(d["validators"].keys()) > 0:
            out_validators = {}
            for validator in d["validators"].keys():
                current = d["validators"][validator]
                c_type = d["type"].lower()
                if validator in ["required"]:
                    if isinstance(
                            current, bool) and (
                            current is True or current is False):
                        out_validators[validator] = current
                elif c_type in ["text", "textarea"]:
                    if validator in [
                            "min",
                            "max"] and isinstance(
                            current,
                            int):
                        out_validators[validator] = current
                    # TODO: add more validation options for text.
                    # maybe subreddit/username?
                elif c_type == "checkbox":
                    if validator in [
                            "min",
                            "max"] and isinstance(
                            current,
                            int):
                        out_validators[validator] = current
                elif c_type == "number":
                    if validator in [
                            "min",
                            "max"] and isinstance(
                            current,
                            int):
                        out_validators[validator] = current
            out["validators"] = out_validators
        ids += out_ids
        sanitized.append(out)

    # set priority of items that aren't prioritized yet
    if max_num is None:
        max_num = 0

    for question in sanitized:
        if question["priority"] is None:
            question["priority"] = max_num + 1
            max_num = max_num + 1

    # sort questions, and save data
    newlist = sorted(sanitized, key=lambda k: k['priority'])
    sanitized_json = json.dumps(newlist)
    g.settings.questions = sanitized_json
    g.settings.required_ids = ids
    db.session.add(g.settings)
    db.session.commit()
    return jsonify(status="OK"), 200


@api.route('/queue')
@mod_required
def queue():
    # returns number of applications remaining
    res = User.query.filter_by(processed=False).count()
    return jsonify(
        text=f"There are currently {res} item(s) in the queue.", number=res), 200


@api.route('/issue_key')
@mod_required
@api_disallowed
def issue_key():
    # issue api token
    run = True
    while run:
        # issue key
        key = "".join(
            random.choices(
                string.ascii_letters +
                string.digits,
                k=32))
        g.user.api_key = key
        try:
            db.session.add(g.user)
            db.session.commit()
            run = False
        except IntegrityError:  # check for uniqueness
            continue
    return g.user.api_key


@api.route('/update_setting', methods=['POST'])
@mod_required
def update_setting():
    # generic method to update settings
    setting_name = request.form["setting"]
    data = request.form["data"]
    if data == "true":
        data = True
    elif data == "false":
        data = False
    if setting_name.lower() not in g.settings.__dict__.keys():
        return bad_request(f"setting field {setting_name} does not exist")
    if setting_name == 'min_age' and data is not None:
        age = age_to_words(int(data))
        setattr(g.settings, 'min_age_word', age)
    setattr(g.settings, setting_name, data)
    db.session.add(g.settings)
    db.session.commit()
    return jsonify(status="OK"), 200


@api.route('/settings')
@mod_required
def settings():
    # returns data about the current settings
    i = inspect(db.engine)
    cols = i.get_columns("Settings")
    ignore = [
        'id',
        'questions',
        'required_ids',
        'response_body',
        'min_age_word']
    out = {}
    for col in cols:
        # don't include things that can't be modified in the settings menu
        if col["name"].lower() in ignore:
            continue

        col_dict = {}
        col_dict["value"] = getattr(g.settings, col["name"])
        col_dict["type"] = type(col_dict["value"]).__name__
        out[col["name"].lower()] = col_dict

    return Response(json.dumps(out), mimetype="application/json")


@api.route('/add_exemption', methods=['POST'])
@mod_required
def add_exemption():
    # adds an exemption of restrictions for a user

    username = request.form["username"]
    if not username:
        return bad_request("username not provided")
    user = User.query.filter(func.lower(username) ==
                             func.lower(username)).first()
    if user:
        user.is_exempt = True
        if len(user.response) > 0:
            user.response = ""
        db.session.add(user)
        db.session.commit()
        return jsonify(status="OK"), 200
    else:
        return bad_request("User does not exist yet")


@api.route('/clear')
@mod_required
def clear():
    # deletes DB rows to make more room

    data = request.get_json(force=True)
    if "all" in data.keys() and data["all"] is True:
        db.session.query(User).delete()
    else:
        User.query.filter_by(processed=True).delete()
    db.session.commit()
    return jsonify(status="OK"), 200


@api.route('/add_mod', methods=["POST"])
@mod_required
def add_mod():
    # adds a user to the list of moderators
    username = request.form["username"]
    user = User.query.filter(func.lower(User.username)
                             == func.lower(username)).first()
    if not user:
        return bad_request("user not found")
    user.form_mod = True
    run = True
    while run:
        # issue key
        key = "".join(
            random.choices(
                string.ascii_letters +
                string.digits,
                k=32))
        user.api_key = key
        try:
            db.session.add(user)
            db.session.commit()
            run = False
        except IntegrityError:  # check for uniqueness
            continue
    db.session.add(user)
    db.session.commit()
    url = url_for('settings', _external=True)
    subj = f"invitation to moderate {g.settings.site_title}"
    body = f"**gadzooks!** u/{g.user.username} has added you as a moderator of {g.settings.site_title}"
    body += f"\n\nclick [here]({url}) to view the site. mod tools will be visible at the top of the page."
    send_message(username, subj, body)
    return jsonify(status="OK"), 200


@api.route('/remove_mod', methods=["POST"])
@mod_required
def remove_mod():
    # removes a user from the list of moderators
    username = request.form["username"]
    user = User.query.filter(func.lower(User.username)
                             == func.lower(username)).first()
    if not user:
        return bad_request("user not found")
    user.form_mod = False
    db.session.add(user)
    db.session.commit()
    return jsonify(status="OK"), 200


@api.route('/process')
@mod_required
def process():
    count = User.query.filter_by(
        submitted=True).filter_by(
        processed=False).count()
    if count == 0:
        return jsonify(text="0 unprocessed form submissions remaining")
    user = User.query.filter_by(
        submitted=True).filter_by(
        processed=False).first()
    body = user.full_body_md
    title = user.response_title
    destination = g.settings.destination_id
    route(title, body, destination)
    user.processed = True
    db.session.add(user)
    db.session.commit()
    return jsonify(text=f"{count-1} unprocessed form submissions remaining")

@api.errorhandler(Exception)
def handle_error(e):
    # generates an error page for all errors
    # source: http://stackoverflow.com/a/29332131
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=code)


@api.route('/api/docs')
def docs():
    return redirect("/mod/api")
