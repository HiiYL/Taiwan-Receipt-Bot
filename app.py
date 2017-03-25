import os
import sys
import json

import requests
from flask import Flask, request

import urllib
import numpy as np
import cv2
import sys

import re
p = re.compile('^.*[A-Z]+[^0-9]*[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][^0-9]*$')

from PIL import Image
import requests
from io import BytesIO

from flask_sqlalchemy import SQLAlchemy

import pyocr
import pyocr.builders

tools = pyocr.get_available_tools()
if len(tools) == 0:
    print("No OCR tool found")
    sys.exit(1)
# The tools are returned in the recommended order of usage

# The tools are returned in the recommended order of usage
tool = tools[0]
print("Will use tool '%s'" % (tool.get_name()))
# Ex: Will use tool 'libtesseract'

langs = tool.get_available_languages()
print("Available languages: %s" % ", ".join(langs))
lang = langs[0]
print("Will use lang '%s'" % (lang))
# Ex: Will use lang 'fra'
# Note that languages are NOT sorted in any way. Please refer
# to the system locale settings for the default language
# to use.


clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
database_dir = 'database/'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    database_dir, 'test.db')

db = SQLAlchemy(app)


lotteryUsers = db.Table('lottery_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('lottery_id', db.Integer, db.ForeignKey('lottery.id'))
)

class User(db.Model):
    # id = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.Integer, primary_key=True)
    lottery_numbers = db.relationship('Lottery',
     secondary=lotteryUsers, backref=db.backref('users',lazy='dynamic'))

    def __init__(self, user_messenger_id):
        self.id = user_messenger_id

    def __repr__(self):
        return '<User %r>' % self.id

class Lottery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    snapshot_path = db.Column(db.String(120))
    lottery_fullcode = db.Column(db.String(20))
    lottery_digit = db.Column(db.String(20))

    def __init__(self, lottery_fullcode, lottery_digit):
        self.lottery_fullcode = lottery_fullcode
        self.lottery_digit = lottery_digit

    def __repr__(self):
        return '<Lottery {}> {}'.format(self.id, self.lottery_digit)




if sys.version_info[0] == 3:
    from urllib.request import urlopen
else:
    # Not Python 3 - today, it is most likely to be Python 2
    # But note that this might need an update when Python 4
    # might be around one day
    from urllib import urlopen


# METHOD #1: OpenCV, NumPy, and urllib
def url_to_image(url):
    # download the image, convert it to a NumPy array, and then read
    # it into OpenCV format
    response = requests.get(url)
    image = Image.open(BytesIO(response.content))
 
    # return the image
    return image

def evaluateImg(image):
    width, height, _ = image.shape
    image = image.astype(np.float32)
    image_processed = process_image(cv2.resize(image,(224,224)))
    out = model.predict(image_processed)

    scores = out[0]
    weights = np.array([1,2,3,4,5,6,7,8,9,10])
    mean_score = (scores * weights).sum(axis=1)

    return mean_score


@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    data = request.get_json()
    log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):  # someone sent us a message

                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    # message_text = messaging_event["message"]["text"]  # the message's text
                    if "attachments" in messaging_event["message"]:
                        send_message(sender_id, "Give me a moment while i process the image...")
                        image_url = messaging_event["message"]["attachments"][0]["payload"]["url"]
                        image = url_to_image(image_url)

                        # print(type(image))

                        ## Preprocessing
                        image = image.convert('L')
                        image = np.array(image)
                        # image = cv2.adaptiveThreshold(image,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,11,2)
                        image = clahe.apply(image)
                        
                        image = Image.fromarray(image)

                        # th3 = cv2.adaptiveThreshold(img,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,11,2)
                        # text = pytesseract.image_to_string(image)
                        text = tool.image_to_string(
                            image,
                            lang=lang,
                            builder=pyocr.builders.TextBuilder()
                        )
                        try:
                            print(text)
                            filtered = [line for line in text.split('\n') if line.strip() and p.match(line)][0]
                            filtered_digits_only = re.sub("\D", "", filtered)


                            send_message(sender_id, "Detected lottery code is : {}".format(filtered)  )

                            sender_id = messaging_event.get("sender").get("id")
                            user = User.query.get(sender_id)
                            if user is None:
                                user = User(sender_id)
                                send_message(sender_id, "Hi there new user, your lottery tickets will now be logged in the system")
                                db.session.add(user)
                                # db.session.commit()

                            # if LotteryNumber.filter_by()
                            lottery = Lottery.query.filter_by(lottery_digit=filtered_digits_only).first()

                            if lottery is None:
                                lottery = Lottery(filtered, filtered_digits_only)
                                lottery.users.append(user)
                                db.session.add(lottery)
                                send_message(sender_id, "Your receipt lottery code has been registered successfully.")
                            else:
                                if lottery.users.filter_by(id=sender_id).first() is None:
                                    lottery.users.append(user)
                                    db.session.add(lottery)
                                else:
                                    send_message(sender_id, "You have already registered this lottery ticket")

                            db.session.commit()
                            
                        except IndexError:
                            send_message(sender_id, "Failed to detect text, sorry :(")

                    elif "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]
                        if "list" in message_text.lower():
                            user = User.query.get(sender_id)
                            if user is None:
                                user = User(sender_id)
                                db.session.add(user)
                                db.session.commit()
                                send_message(sender_id, "Hi there new user, submit images of receipts to get started. ")
                            else:
                                if user.lottery_numbers is None:
                                    send_message(sender_id, "You have not submitted any lottery numbers")
                                else:
                                    response = "Here are the lottery numbers you have submitted so far \n"
                                    for lottery_number in user.lottery_numbers:
                                        response += (lottery_number.lottery_fullcode + "\n")
                                    send_message(sender_id, response)


                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(message):  # simple wrapper for logging to stdout on heroku
    print(str(message))
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=False)


                    # sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    # recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    # if "text" in messaging_event["message"]:
                    #     message_text = messaging_event["message"]["text"]  # the message's text
                    #     send_message(sender_id, "got it ( a text ), thanks!")
                    # elif "attachments" in messaging_event["message"]:
                    #     image_url = messaging_event["message"]["attachments"][0]["payload"]["url"]
                    #     print(image_url)
                    # else:
                    #     send_message(sender_id, "got it ( unknown ), thanks!")