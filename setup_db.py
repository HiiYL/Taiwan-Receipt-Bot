from app import db
from app import User
from app import Lottery

db.drop_all()
db.create_all()
user = User('1598315673512744')
db.session.add(user)
db.session.commit()
lottery = Lottery('TA-72163500', '72163500')
lottery.users.append(user)
db.session.add(lottery)
db.session.commit()
Lottery.query.all()

lottery = Lottery.query.filter_by(lottery_digit='72163500').first()