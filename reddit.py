from urllib.parse import urlencode
import os
import re
import requests
import requests.auth
import time


def verify_identity(code):
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    headers = {"User-Agent": user_agent}
    client_id = os.environ.get('REDDIT_FRONTEND_CLIENT_ID')
    client_secret = os.environ.get('REDDIT_FRONTEND_CLIENT_SECRET')
    auth = (client_id, client_secret)
    params = {"grant_type": "authorization_code",
              "code": code,
              "redirect_uri": os.environ.get('REDDIT_FRONTEND_REDIRECT_URI')}
    result = requests.post(
    "https://www.reddit.com/api/v1/access_token",
    headers=headers,
    auth=auth,
     params=params)

    auth_dict = result.json()
    if 'error' in auth_dict:
        return None

    headers = {"User-Agent": user_agent,
               "Authorization": f"bearer {auth_dict['access_token']}"}
    user_page = requests.get("https://oauth.reddit.com/api/v1/me",
                             headers=headers)
    me_dict = user_page.json()

    return {'name': me_dict['name'],
            'created': me_dict['created'],
            'link_karma': me_dict['link_karma'],
            'comment_karma': me_dict['comment_karma'],
            'combined_karma': (int(me_dict['comment_karma']) + int(me_dict['link_karma'])),
            'is_mod': me_dict['is_mod'],
            'is_gold': me_dict['is_gold'],
            'has_verified_email': me_dict['has_verified_email']}


def generate_oauth_url(state, next_path='form', scopes=["identity"]):
    # generates a OAuth URL for reddit
    base = "https://www.reddit.com/api/v1/authorize?"
    params = {"client_id": os.environ.get('REDDIT_FRONTEND_CLIENT_ID'),
              "response_type": "code",
              "state": state + "|" + next_path,
              "redirect_uri": os.environ.get('REDDIT_FRONTEND_REDIRECT_URI'),
              "duration": "temporary",
              "scope": ",".join(scopes)}
    return base + urlencode(params)


def get_bot_auth():
    # Creates a bot authorization token
    client_id = os.environ.get("REDDIT_BACKEND_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_BACKEND_CLIENT_SECRET")
    username = os.environ.get("REDDIT_BACKEND_USERNAME")
    password = os.environ.get("REDDIT_BACKEND_PASSWORD")
    user_agent = os.environ.get("REDDIT_USER_AGENT")

    client_auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    post_data = {"grant_type": "password",
                 "username": username,
                 "password": password}
    headers = {"User-Agent": user_agent}
    response = requests.post("https://www.reddit.com/api/v1/access_token",
                             auth=client_auth,
                             data=post_data,
                             headers=headers)
    return response.json()['access_token']


def submit_post(title, text, subreddit):
    bearer = "bearer " + get_bot_auth()
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    headers = {"Authorization": bearer, "User-Agent": user_agent}
    parameters = {"api_type": "json",
                  "kind": "self",
                  "send_replies": False,
                  "sr": subreddit,
                  "text": text,
                  "title": title}
    response = requests.post("https://oauth.reddit.com/api/submit",
                             headers=headers,
                             data=parameters)
    try:
        url = response.json()['json']['data']['url']
    except KeyError:
        url = "error"
    return url


def post_comment(thread, text):
    bearer = "bearer " + get_bot_auth()
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    headers = {"Authorization": bearer, "User-Agent": user_agent}

    # check for correct prefixing. assume thread unless stated otherwise.
    acceptable_prefixes = ['t1_', 't3_', 't4_']
    for prefix in acceptable_prefixes:
        if thread.startswith(prefix):
            break
    else:
        return

    parameters = {"api_type": "json",
                  "send_replies": False,
                  "text": text}
    response = requests.post("https://oauth.reddit.com/api/submit",
                             headers=headers,
                             data=parameters)
    try:
        url = response.json()['json']['data']['url']
    except KeyError:
        url = "error"
    return url


def user_info(username):
    bearer = "bearer " + get_bot_auth()
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    headers = {"Authorization" : bearer, "User-Agent" : user_agent}
    out = requests.get("https://oauth.reddit.com/user/{0}/about.json".format(username), headers=headers)

    combined = int(me_dict['comment_karma']) + int(me_dict['link_karma'])
    try:
        me_dict =  out.json()['data']
        reg_dict_out = {'name': me_dict['name'],
                        'created': me_dict['created'],
                        'link_karma': me_dict['link_karma'],
                        'comment_karma': me_dict['comment_karma'],
                        'combined_karma': combined,
                        'is_mod': me_dict['is_mod'],
                        'is_gold': me_dict['is_gold'],
                        'has_verified_email': me_dict['has_verified_email']}
        return reg_dict_out
    except:
        try:
            me_dict =  out.json()['data']
            susp_dict_out = {'name': me_dict['name'],
                             'is_suspended': me_dict['is_suspended']}
            return susp_dict_out
        except:
            return out.json()

def send_message(user, subject, message):
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    try:
        bearer = "bearer " + get_bot_auth()
        headers = {"Authorization": bearer, "User-Agent": user_agent}
        parameters = {"api_type": "json",
                      "subject": subject,
                      "text": message,
                      "to": user}
        response = requests.post("https://oauth.reddit.com/api/compose", headers=headers, data=parameters)
        return "success"
    except:
        return "failure"


def route(title, body, destination):
    if destination.startswith('t1_') or destination.startswith(
        't3_') or destination.startswith('t4_'):
        return post_comment(destination, body)
    elif 'r/' in destination:
        exp = re.compile(r"\/?r\/(.+)")
        sr_name = exp.findall(destination)[0]
        submit_post(title, body, sr_name)
    else:
        send_message(destination, title, body)
