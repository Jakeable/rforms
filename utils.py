from flask import jsonify


def age_to_words(seconds):
    multipliers = [1, 60, 60, 24, 7, 52]
    words = ['seconds', 'minutes', 'hours', 'days', 'weeks', 'years']
    current = 1
    for multiplier, word in zip(multipliers, words):
        current *= multiplier
        value = seconds / current
        if value >= 1:
            if round(value, 1) == 1:
                word = word[:-1]
            if round(value, 1) % 1 == 0:
                value = int(value)
            age = str(round(value, 2)) + " " + word
    return age


def bad_request(message):
    # custom response type for invalid requests
    # http://stackoverflow.com/a/21297608/
    response = jsonify({'message': message})
    response.status_code = 400
    return response
