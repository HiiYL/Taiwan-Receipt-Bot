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
p = re.compile('^.*[A-Z]+[^0-9]*[oOlI0-9][oOlI0-9][oOlI0-9][oOlI0-9][oOlI0-9][oOlI0-9][oOlI0-9][oOlI0-9][^0-9]*$')
alphabet_only = re.compile('[^a-zA-Z]')


from PIL import Image
import requests
from io import BytesIO

from flask_sqlalchemy import SQLAlchemy
import datetime

from lxml import html

# import pyocr
# import pyocr.builders

# tools = pyocr.get_available_tools()
# if len(tools) == 0:
#     print("No OCR tool found")
#     sys.exit(1)
# # The tools are returned in the recommended order of usage

# # The tools are returned in the recommended order of usage
# tool = tools[0]
# print("Will use tool '%s'" % (tool.get_name()))
# # Ex: Will use tool 'libtesseract'

# langs = tool.get_available_languages()
# print("Available languages: %s" % ", ".join(langs))
# lang = langs[0]
# print("Will use lang '%s'" % (lang))
# # Ex: Will use lang 'fra'
# # Note that languages are NOT sorted in any way. Please refer
# # to the system locale settings for the default language
# # to use.

from tesserocr import PyTessBaseAPI
import tesserocr


api = tesserocr.PyTessBaseAPI()
api.SetVariable("tessedit_char_whitelist", "ABCDEFGHLMNOPQRSTUVWXYZ0123456789- ")


clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
database_dir = 'database/'
snapshots_dir = 'receipt_snapshots/'

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
    created_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, lottery_fullcode, lottery_digit):
        self.lottery_fullcode = lottery_fullcode
        self.lottery_digit = lottery_digit

    def setSnapshot(snapshot_filename):
        self.snapshot_path = snapshot_filename


    def __repr__(self):
        return '<Lottery {}> {} - {}'.format(self.id, self.lottery_digit, self.created_date)




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

                        width, height = image.size

                        # print("DPI = {}".format(image.info['dpi']))

                        image = image.resize((width * 2, height * 2))

                        # print(type(image))

                        ## Preprocessing
                        # image = image.convert('L')
                        image = np.array(image)

                        # image = cv2.resize(image, (width * 2, height * 2))


                        image = cv2.fastNlMeansDenoisingColored(image,None,10,10,7,21)

                        # image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

                        # image = cv2.GaussianBlur(image,(5,5),0)
                        # _,image = cv2.threshold(image,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)

                        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)

                        l, a, b = cv2.split(lab)

                        cl = clahe.apply(l)
                        limg = cv2.merge((cl,a,b))

                        image = cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)

                        # image = clahe.apply(image)
                        
                        image = Image.fromarray(image)

                        snapshot_path = os.path.join(snapshots_dir,
                         "test2.jpg")
                        image.save(snapshot_path)
                        api.SetImage(image)
                        text = api.GetUTF8Text()

                        print(text)
                        # text = tool.image_to_string(
                        #     image,
                        #     lang=lang,
                        #     builder=pyocr.builders.TextBuilder()
                        # )
                        try:
                            filtered = [line for line in text.split('\n') if line.strip() and p.match(line)][0]
                            items_to_remove = 0


                            special_cases = ['o', 'O', 'l', 'I']
                            for i in reversed(filtered):
                                if i.isdigit() or (i in special_cases):
                                    break
                                else:
                                    items_to_remove = items_to_remove + 1

                            if items_to_remove > 0:
                                print("[!] Removing {} invalid non digit character from end of string".format(items_to_remove))

                            for i in range(items_to_remove):
                                filtered = filtered[:-1]

                            numbers_only = filtered[-8:]
                            numbers_only = numbers_only.replace('o','0').replace('O','0').replace('l','1').replace('I','1')

                            alphabets = filtered[:-8]
                            alphabets = alphabet_only.sub('', alphabets)[-2:] + " "

                            filtered =  alphabets + numbers_only

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

                                lottery.snapshot_path = image_url

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
                        user = User.query.get(sender_id)
                        if user is None:
                            user = User(sender_id)
                            db.session.add(user)
                            db.session.commit()
                            send_message(sender_id, "Hi there new user, submit images of receipts to get started. ")
                        elif user.lottery_numbers is None:
                            send_message(sender_id, "You have not submitted any lottery numbers.")
                            send_message(sender_id,
                             "Hello there, to get started, type one of the following commands or submit a photo of a receipt \n \
                              List  - List receipts submit so far \
                              Image - List receipts and associated images \
                              Check - Check your submitted receipts to see if you have won something")
                        elif "image" in message_text.lower():
                            response = "Here are the lottery numbers you have submitted so far \n"
                            for lottery_number in user.lottery_numbers:
                                send_message(sender_id,lottery_number.lottery_fullcode)
                                send_image(sender_id, lottery_number.snapshot_path)
                        elif "list" in message_text.lower():
                            response = "Here are the lottery numbers you have submitted so far \n"
                            for lottery_number in user.lottery_numbers:
                                response += (lottery_number.lottery_fullcode + "\n")
                            send_message(sender_id, response)
                        elif "check" in message_text.lower():

                            send_message(sender_id, "No problem, i will now check if you have won anything...")
                            page = requests.get("http://invoice.etax.nat.gov.tw")
                            tree = html.fromstring(page.content)
                            codes = tree.xpath('//*[@id="area1"]/table/tr/td[2]/span/text()')
                            extra_special_prize = codes[0]
                            special_prize = codes[1]

                            first_prize = codes[2].split("、")

                            first_prize_earnings = [40000, 10000, 4000, 1000, 200 ]

                            consolation_prize = codes[3]
                            consolation_prize_earnings = [200]
                            send_message(sender_id, 
                                '\n'.join(["All data stored, these are the information i have retrieved:",
                                    "Extra Special Award",extra_special_prize,
                                    "Special Award", special_prize,
                                    "First Place", ' '.join([first_prize[0], first_prize[1], first_prize[2]]),
                                    "Consolation Prize", consolation_prize]))

                            sum_winnings = 0
                            for lottery_number in user.lottery_numbers:
                                current_code = lottery_number.lottery_digit
                                if current_code == extra_special_prize:
                                    send_message(sender_id, "Congratulations, You have won the extra special prize amounting to 10 000 000 TWD!")
                                    send_message(sender_id,lottery_number.lottery_fullcode)
                                    sum_winnings += 10000000
                                    if lottery_number.snapshot_path is not None:
                                        send_image(sender_id, lottery_number.snapshot_path)
                                elif current_code == special_prize:
                                    send_message(sender_id, "Congratulations, You have won the special prize amounting to 2 000 000 TWD!")
                                    send_message(sender_id,lottery_number.lottery_fullcode)
                                    sum_winnings += 2000000
                                    if lottery_number.snapshot_path is not None:
                                        send_image(sender_id, lottery_number.snapshot_path)
                                else:
                                    won = False
                                    for prize in first_prize:
                                        if won:
                                            break
                                        for i in range(6):
                                            if (prize[i:] == current_code[i:]):
                                                send_message(sender_id, "Congratulations, You have won the {}th prize amounting to {}!".format(i + 1, first_prize_earnings[i] ))
                                                send_message(sender_id,lottery_number.lottery_fullcode)
                                                send_image(sender_id, lottery_number.snapshot_path)
                                                sum_winnings += first_prize_earnings[i]
                                                won = True
                                                break
                                    if current_code[5:] == consolation_prize:
                                        send_message(sender_id, "Congratulations, You have won the consolation prize amounting to 200 TWD!".format(i + 1))
                                        send_message(sender_id,lottery_number.lottery_fullcode)
                                        send_image(sender_id, lottery_number.snapshot_path)
                                        sum_winnings += 200
                            if sum_winnings > 0:
                                send_image(sender_id, "In total, you have won {} :)".format(sum_winnings))
                            else:
                                send_image(sender_id, "Unfortunately you did not win anything :(")
                        else:
                            send_message(sender_id,
                             "Hello there, to get started, type one of the following commands or submit a photo of a receipt \n \
                              List  - List receipts submit so far \
                              Image - List receipts and associated images \
                              Check - Check your submitted receipts to see if you have won something")



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


def send_image(recipient_id, image_path):
    log("sending image to {recipient}: {path}".format(recipient=recipient_id, path=image_path))
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
            "attachment":{
              "type":"image",
              "payload":{
                "url":image_path
              }
            }
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
    app.run(debug=False, port=5001)


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