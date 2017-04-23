from flask.ext.sqlalchemy import SQLAlchemy
import time

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'User'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, unique=True)
    post_karma = db.Column(db.Integer)
    comment_karma = db.Column(db.Integer)
    created_utc = db.Column(db.Integer)
    is_mod = db.Column(db.Boolean)
    form_mod = db.Column(db.Boolean, default=False)
    verified_email = db.Column(db.Boolean)
    response = db.Column(db.String)
    full_body_md = db.Column(db.String)
    full_body_html = db.Column(db.String)
    response_title = db.Column(db.String)
    submitted = db.Column(db.Boolean, default=False)
    processed = db.Column(db.Boolean, default=False)
    form_reply_link = db.Column(db.String)
    api_key = db.Column(db.String, unique=True)
    is_exempt = db.Column(db.Boolean, default=False)
    eligible_for_exemption = db.Column(db.Boolean)
    last_login = db.Column(db.Integer, default=int(time.time()))
    last_api_access = db.Column(db.Integer)


class Settings(db.Model):
    __tablename__ = 'Settings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    accepting = db.Column(db.Boolean, default=False)  # form enabled/disabled
    # homepage
    site_title = db.Column(db.String, default="subreddit form site")
    welcome_body = db.Column(
        db.String,
        default="welcome to the form site!")  # homepage information
    # form page
    instructions = db.Column(db.String, default="Please fill this form out.")
    # questions
    questions = db.Column(db.String, default="[]")
    # number of random IDs to generate
    required_ids = db.Column(db.Integer, default=0)
    # form config
    # karma a user needs to view the form
    min_karma = db.Column(db.Integer, default=-100)
    # age in seconds an account has to be in order to view the form
    min_age = db.Column(db.Integer, default=-100)
    # display phrase for how old an account needs to be
    min_age_word = db.Column(db.String, default="")
    expose_mins = db.Column(db.Boolean, default=True)
    preview_allowed = db.Column(db.Boolean, default=True)
    # form output
    destination_id = db.Column(db.String, default="")  # reddit thing id
    response_title = db.Column(db.String, default="u/{username}")
    response_body = db.Column(db.String, default="{response}")
    message_user = db.Column(db.Boolean, default=True)
    message_subject = db.Column(db.String, default="Form submission received")
    message_body = db.Column(
        db.String,
        default="Hi {username}, we have received your submission.")
    success_url = db.Column(db.String, default="https://www.reddit.com/")
    contact_destination = db.Column(db.String, default="me")
    google_analytics_enabled = db.Column(db.Boolean, default=False)
    google_analytics_id = db.Column(db.String, default="")
