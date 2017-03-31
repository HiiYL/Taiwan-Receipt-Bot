from app import db
from app import User
from app import Lottery

db.drop_all()
db.create_all()
user = User('1409822159088386')
db.session.add(user)
db.session.commit()
lottery = Lottery('TA-82885130', '82885130')
lottery.users.append(user)
db.session.add(lottery)
db.session.commit()
Lottery.query.all()

lottery = Lottery.query.filter_by(lottery_digit='82885130').first()