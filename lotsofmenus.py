from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Store, Base, MenuItem, User

engine = create_engine('sqlite:///onlinestore.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create dummy user
User1 = User(name="Raga", email="raga@gmail.com",
             picture='')
session.add(User1)
session.commit()

# Menu for UrbanBurger
store1 = Store(user_id=1, name="ALL Groceries")

session.add(store1)
session.commit()

menuItem2 = MenuItem(user_id=1, name="Roma Tomatoes",
                     description="Fresh Red locally grown Tomatoes",
                     price="$1.50 per lb",
                     course="Vegetables", store=store1)

session.add(menuItem2)
session.commit()


menuItem1 = MenuItem(user_id=1, name="Lemons",
                     description="Juicy fresh locally grown", price="$.99 each",
                     course="Vegetables", store=store1)

session.add(menuItem1)
session.commit()

menuItem2 = MenuItem(user_id=1, name="Cilantro",
                     description="fresh locally grown",
                     price="$.50 each",
                     course="Vegetables", store=store1)

session.add(menuItem2)
session.commit()

menuItem3 = MenuItem(user_id=1, name="Green Bell Peppers",
                     description="fresh locally grown",
                     price="$3.99", course="Vegetables", store=store1)

session.add(menuItem3)
session.commit()

menuItem4 = MenuItem(user_id=1, name="Chicken",
                     description="fresh chicken non caged",
                     price="$7.99", course="Meat", store=store1)

session.add(menuItem4)
session.commit()

menuItem5 = MenuItem(user_id=1, name="Turkey",
                     description="100% no preservatives fresh Turkey",
                     price="$11.99", course="Meat", store=store1)

session.add(menuItem5)
session.commit()

menuItem6 = MenuItem(user_id=1, name="H&S shampoo", description="Anti Dnadruff Shampoo",
                     price="$.99", course="Pharma", store=store1)

session.add(menuItem6)
session.commit()

menuItem7 = MenuItem(user_id=1, name="Body soap",
                     description="deo soap prevents from bad odors",
                     price="$3.49", course="Pharma", store=store1)

session.add(menuItem7)
session.commit()

print "added menu items!"
