from flask import (Flask, abort, g, jsonify, redirect,
                   render_template, request, session, url_for)
from models import db, User, Settings
from sqlalchemy.exc import IntegrityError
from flask_sslify import SSLify
from decorators import login_required, mod_required, api_disallowed
from werkzeug.exceptions import HTTPException
from reddit import generate_oauth_url, send_message, route, verify_identity
from utils import age_to_words, bad_request
import json
import os
import uuid
import time
import random
import string
import markdown

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# HTTPS all the links
sslify = SSLify(app)

# SQLAlchemy intiialization
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("://", "ql://", 1)
db.init_app(app)

# import/register blueprints
from api import api
from mod import mod
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(mod, url_prefix='/mod')


@app.before_first_request
def startup():
    db.create_all()
    # create settings object if it doesn't exist
    settings = Settings.query.first()
    if not settings:
        s = Settings()
        # load example questions json
        with open("data/question_example.json", "r") as example:
            s.questions = example.read()
        # detect number of response IDs required
        data = json.loads(s.questions)
        ids = len(data)
        for d in data:
            if "data" in d.keys():
                ids += len(d["data"])
        s.required_ids = ids
        # set example response text
        with open("data/response_example.txt", "r") as resp:
            s.response_body = resp.read()
        db.session.add(s)
        db.session.commit()


@app.before_request
def load_g():
    # load globals
    s = Settings.query.first()
    g.settings = s
    try:
        username = session['username']
    except KeyError:
        username = None
    g.api_login = False
    user = User.query.filter_by(username=username).first()
    if user:
        g.user = user
    else:
        g.user = None
    try:
        api_key = request.headers.get('X-Api-Key', None)
        if not api_key:
            api_key = request.args.get('key', None)
        if api_key and not g.user:
            g.user = User.query.filter_by(api_key=api_key).first()
            g.api_login = True
    except KeyError:
        g.api_key = None
    if g.user and not g.api_login:
        g.last_login = int(time.time())
    elif g.user and g.api_login:
        g.last_api_access = int(time.time())


@app.route('/')
def index():
    # homepage
    domain = request.url_root
    disp_url = request.headers['Host']
    return render_template("index.html", domain=domain, disp_url=disp_url)


@app.route('/logout')
def logout():
    # clears session data, redirects user to homepage
    session.clear()
    return redirect(url_for('index'))


@app.route('/auth')
def auth():
    # set user cookie & redirect to reddit for OAuth
    session['user'] = str(uuid.uuid4())
    next_path = request.args.get('next', 'form')
    return redirect(
        generate_oauth_url(
            session['user'],
            next_path=next_path),
        302)


@app.route('/callback')
def callback():
    # receives info from reddit in a callback url, processes data

    # check that the request originated from the site
    state_params = request.args.get('state').split("|")
    state = state_params[0]
    if state != str(session['user']):
        return redirect(url_for('redir'))

    # get or update basic user info
    code = request.args.get('code')
    session['oauthcode'] = code
    user_dict = verify_identity(session['oauthcode'])
    session['username'] = user_dict['name']
    u = User.query.filter_by(username=session['username']).first()
    if not u:
        u = User(
            username=user_dict['name'],
            post_karma=user_dict['link_karma'],
            comment_karma=user_dict['comment_karma'],
            created_utc=user_dict['created'],
            is_mod=user_dict['is_mod'],
            verified_email=user_dict['has_verified_email'])
        # make the first created account a form moderator
        db.session.add(u)
        db.session.commit()
        if u.id == 1:
            u.form_mod = True
            run = True
            while run:
                # issue key
                allowed = string.ascii_letters + string.digits
                key = "".join(random.choices(allowed, k=32))
                u.api_key = key
                try:
                    db.session.add(u)
                    db.session.commit()
                    run = False
                except IntegrityError:  # check for uniqueness
                    continue

    else:
        u.post_karma = user_dict['link_karma']
        u.comment_karma = user_dict['comment_karma']
        u.created_utc = user_dict['created']
        u.is_mod = user_dict['is_mod']
        u.verified_email = user_dict['has_verified_email']
    db.session.add(u)
    db.session.commit()
    return redirect(url_for(state_params[1]))


@app.route('/form', methods=['GET', 'POST'])
@login_required
@api_disallowed
def form():
    # check user eligibility to fill out form
    if not g.settings.accepting:
        msg = "This form is not accepting responses."
        return render_template("error.html", short_message=msg)

    simulate = request.args.get('simulatefailure', False)
    issues = []
    eligible_for_exemption = False
    if not g.user.is_exempt:
        if (g.user.post_karma +
                g.user.comment_karma) < g.settings.min_karma or simulate:
            err_msg = f"Combined karma (post + comment karma) is too low. "
            if g.settings.expose_mins:
                err_msg += f"Accounts must have at least {g.settings.min_karma} karma to view this form."
            issues.append(err_msg)
        if (time.time() - g.user.created_utc) < g.settings.min_age or simulate:
            err_msg = f"Account is not old enough. "
            if g.settings.expose_mins:
                err_msg += f"Accounts must be at least {g.settings.min_age_word} old to view this form."
            issues.append(err_msg)
        if g.user.submitted or simulate:
            issues.append('You have already submitted an application')
    if issues:
        return render_template('issue.html', errors=issues)

    # render form
    if request.method == 'GET':
        # load form if data was already copied
        try:
            json_data = json.loads(g.user.response)
            return render_template("form.html", data=json_data)
        except (TypeError, ValueError):
            pass

        ids = []
        copy = json.loads(g.settings.questions)
        while len(ids) < g.settings.required_ids:
            s = ''.join(
                random.choices(
                    string.ascii_letters +
                    string.digits,
                    k=4))
            if s not in ids:
                ids.append(s)

        for q in copy:
            q["id"] = ids.pop()
            if "data" in q.keys():
                # add ids to data
                new_data = []
                for d in q["data"]:
                    new_data.append([ids.pop(), d])
                q["data"] = new_data

            # generate validator descriptions
            if "validators" in q.keys():
                validators = q["validators"]
                validator_words = []
                for validator in validators.keys():
                    q_type = q["type"].lower()
                    if validator.lower() == "min":
                        if q_type in ["text", "textarea"]:
                            phrase = "Must be longer than {} characters".format(
                                validators[validator])
                            validator_words.append(phrase)
                        elif q_type in ["number"]:
                            phrase = "Number must be bigger than {}.".format(
                                validators[validator])
                            validator_words.append(phrase)
                        elif q_type in ["checkbox"]:
                            phrase = "At least {} need to be selected".format(
                                validators[validator])
                            validator_words.append(phrase)
                    elif validator.lower() == "max":
                        if q_type in ["text", "textarea"]:
                            phrase = "Must be shorter than {} characters".format(
                                validators[validator])
                            validator_words.append(phrase)
                        elif q_type in ["number"]:
                            phrase = "Number must be smaller than {}.".format(
                                validators[validator])
                            validator_words.append(phrase)
                        elif q_type in ["checkbox"]:
                            phrase = "No more than {} may be selected".format(
                                validators[validator])
                            validator_words.append(phrase)
                    elif validator.lower() == "required":
                        phrase = "Requires a response."
                        validator_words.append(phrase)
                if len(validator_words) > 0:
                    q["validator_words"] = validator_words
            q["response"] = ""

        g.user.response = json.dumps(copy)
        db.session.add(g.user)
        db.session.commit()
        return render_template("form.html", data=copy)

    # process form data
    template = json.loads(g.user.response)
    has_error = False
    for question in template:
        # clear errors
        if "error" in question.keys():
            del question["error"]

        # parse input based on question type
        q_type = question["type"]
        if q_type in ["text", "textarea", "dropdown"]:
            resp = request.form.get(question["id"])
        elif q_type == "radio":
            resp = []
            resp_id = request.form.get(question["id"])
            for option in question["data"]:
                if option[0] == resp_id:
                    resp = option[1]
                    break
        elif q_type == "number":
            resp = int(request.form.get(question["id"]))
        elif q_type == "checkbox":
            resp = request.form.getlist(question["id"])
            data = question["data"]
            out_data = []
            for response in resp:
                for d in data:
                    if response == d[0]:
                        out_data.append(d[1])
            resp = out_data

        question["response"] = resp
        # validate input
        if "validators" in question.keys():
            validators = question["validators"]

            # minimum length validator
            if "min" in validators.keys():
                min_len = validators["min"]
                if q_type in [
                    "text",
                    "textarea",
                        "radio"] and len(resp) < min_len:
                    msg = f"Response was too short. Minimum length is {min_len} characters."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)
                elif q_type == "number" and resp < min_len:
                    msg = f"Response was too small. Number must be greater than {min_len}."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)
                elif q_type == "checkbox" and len(resp) < min_len:
                    msg = f"Response was too short. At least {min_len} checkboxes must be checked."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)

            # max length validator
            if "max" in validators.keys():
                max_len = validators["max"]
                if q_type in [
                    "text",
                    "textarea",
                        "radio"] and len(resp) > max_len:
                    msg = f"Response was too long. Maximum length is {max_len} characters."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)
                elif q_type == "number" and resp > max_len:
                    msg = f"Response was too large. Number must be smaller than {max_len}."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)
                elif q_type == "checkbox" and len(resp) > max_len:
                    msg = f"Response was too long. No more than {min_len} checkboxes may be checked."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)

            # required validator
            if "required" in question["validators"]:
                unfilled = False
                if q_type in [
                    "text",
                    "textarea",
                    "radio",
                        "checkbox"] and len(resp) == 0:
                    unfilled = True
                if resp is None or unfilled:
                    msg = "A reply to this question is required."
                    if "error" not in question.keys():
                        question["error"] = [msg]
                        has_error = True
                    else:
                        question["error"].append(msg)

    # return errors for user to fix
    if has_error:
        return render_template("form.html", data=template, settings=g.settings)

    # save data and mark for processing
    g.user.response = json.dumps(template)
    out = ""
    counter = 1
    for question in template:
        out += f"\n**{counter}. {question['text']}**\n\n"
        if not isinstance(question['response'], (list, tuple)):
            out += "\n\n".join("> " +
                               line for line in str(question['response']).splitlines())
        else:
            out += "\n".join(">* " + line for line in question['response'])
        out += "\n"
        counter += 1
    body = g.settings.response_body

    # calculate age in words
    age = age_to_words(time.time() - g.user.created_utc)

    combined = g.user.post_karma + g.user.comment_karma
    formatted_body = body.format(username=g.user.username,
                                 post_karma=g.user.post_karma,
                                 comment_karma=g.user.comment_karma,
                                 combined_karma=combined,
                                 age=age,
                                 is_verified=g.user.verified_email,
                                 is_mod=g.user.is_mod,
                                 response=out)
    g.user.full_body_md = formatted_body
    g.user.full_body_html = markdown.markdown(formatted_body)
    title_template = g.settings.response_title
    formatted_title = title_template.format(username=g.user.username,
                                            post_karma=g.user.post_karma,
                                            comment_karma=g.user.comment_karma,
                                            combined_karma=combined,
                                            age=age,
                                            is_verified=g.user.verified_email,
                                            is_mod=g.user.is_mod)
    g.user.response_title = formatted_title
    g.user.submitted = True
    g.user.is_exempt = False  # clear exemption after form is submitted
    db.session.add(g.user)
    db.session.commit()

    if g.settings.message_user:
        subject = g.settings.message_subject.format(
            username=g.user.username,
            post_karma=g.user.post_karma,
            comment_karma=g.user.comment_karma,
            combined_karma=combined,
            age=age,
            is_verified=g.user.verified_email,
            is_mod=g.user.is_mod)
        body = g.settings.message_body.format(
            username=g.user.username,
            post_karma=g.user.post_karma,
            comment_karma=g.user.comment_karma,
            combined_karma=combined,
            age=age,
            is_verified=g.user.verified_email,
            is_mod=g.user.is_mod)
        send_message(g.user.username, subject, body)

    return render_template("success.html", settings=g.settings)


@app.route('/preview')
def preview():
    # a view-only preview of the form
    if not g.settings.preview_allowed and (not g.user and not g.user.form_mod):
        return abort(403)
    copy = json.loads(g.settings.questions)
    for q in copy:
        q["id"] = ""
        if "data" in q.keys():
            # add ids to data
            new_data = []
            for d in q["data"]:
                new_data.append(["", d])
            q["data"] = new_data
        q["response"] = None
    return render_template("form.html", data=copy, preview=True)


@app.route('/contact')
def contact():
    url = f"https://www.reddit.com/message/compose?to={g.settings.contact_destination}"
    return redirect(url)


@app.route('/docs/<location>')
def docs(location):
    url = f"https://github.com/Jakeable/rforms/wiki/{location}"
    return redirect(url)

@app.errorhandler(Exception)
def handle_error(e):
    # generates an error page for all errors
    # source: http://stackoverflow.com/a/29332131
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    smsg = "An error occurred when attempting to serve this page."
    return render_template("error.html", errno=code, short_message=smsg)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
