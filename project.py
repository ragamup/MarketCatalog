from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Store, MenuItem, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from functools import wraps
from flask import Flask, render_template, request, redirect, jsonify, url_for, flash

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Restaurant Menu"


# Connect to Database and create database session
engine = create_engine('sqlite:///onlinestore.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    code = request.data

    try:
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    response = h.request(url, 'GET')[1]
    str_response = response.decode('utf-8')
    result = json.loads(str_response)

    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps(
            'Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        # return response

    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['provider'] = 'google'
    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px; \
                            -webkit-border-radius: 150px;-moz-border-radius: \
                                150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    return output


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


@app.route('/gdisconnect')
def gdisconnect():
            # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        # Reset the user's sesson.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        login_session.clear()

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        # return response
        return redirect(url_for('showStores'))
    else:
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/logout')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
        login_session.clear()
        flash("You have successfully been logged out.")
        return redirect(url_for('showStores'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showStores'))


@app.route('/store/<int:store_id>/menu/JSON')
def storeMenuJSON(store_id):
    store = session.query(Store).filter_by(id=store_id).one()
    items = session.query(MenuItem).filter_by(
        store_id=store_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/store/<int:store_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(store_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


@app.route('/store/JSON')
def storesJSON():
    stores = session.query(Store).all()
    return jsonify(stores=[r.serialize for r in stores])


@app.route('/')
@app.route('/store/')
def showStores():
    stores = session.query(Store).order_by(asc(Store.name))
    if 'username' not in login_session:
        return render_template('publicstores.html',
                               store=stores)
    else:
        return render_template('stores.html', store=stores)


@app.route('/store/new/', methods=['GET', 'POST'])
@login_required
def newStore():
    if request.method == 'POST':
        newStore = Store(
            name=request.form['name'], user_id=login_session['user_id'])
        session.add(newStore)
        flash('New store %s Successfully Created' % newStore.name)
        session.commit()
        return redirect(url_for('showStores'))
    else:
        return render_template('newStore.html')


@app.route('/store/<int:store_id>/edit/', methods=['GET', 'POST'])
@login_required
def editStore(store_id):
    editedStore = session.query(
        Store).filter_by(id=store_id).one()
    if editedStore.user_id != login_session['user_id']:
        return "<h2>You do not have permission."\
            "Only the user who created store can edit</h2>"
    if request.method == 'POST':
        if request.form['name']:
            editedStore.name = request.form['name']
            flash('Store Successfully Edited %s' % editedStore.name)
            return redirect(url_for('showStores'))
    else:
        return render_template('editStore.html',
                               store=editedStore)


@app.route('/store/<int:store_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteStore(store_id):
    storeToDelete = session.query(
        Store).filter_by(id=store_id).one()
    if storeToDelete.user_id != login_session['user_id']:
        return "<h2>You do not have permission."\
            "Only the user who created store can delete</h2>"
    if request.method == 'POST':
        session.delete(storeToDelete)
        flash('%s Successfully Deleted' % storeToDelete.name)
        session.commit()
        return redirect(url_for('showStores',
                                store_id=store_id))
    else:
        return render_template('deleteStore.html',
                               store=storeToDelete)


@app.route('/store/<int:store_id>/')
@app.route('/store/<int:store_id>/menu/')
def showMenu(store_id):
    store = session.query(Store).filter_by(id=store_id).one()
    creator = getUserInfo(store.user_id)
    items = session.query(MenuItem).filter_by(
        store_id=store_id).all()
    if 'username' not in login_session or creator.id != login_session.get('user_id'):
        return render_template('publicmenu.html', items=items,
                               store=store, creator=creator)
    else:
        return render_template('menu.html', items=items,
                               store=store, creator=creator)


@app.route('/store/<int:store_id>/menu/new/',
           methods=['GET', 'POST'])
@login_required
def newMenuItem(store_id):
    store = session.query(Store).filter_by(id=store_id).one()
    if login_session['user_id'] != store.user_id:
        return "<h2>You do not have permission."\
            "Only the user who created store can add</h2>"
    if request.method == 'POST':
        newItem = MenuItem(name=request.form['name'],
                           description=request.form['description'],
                           price=request.form['price'],
                           course=request.form['course'],
                           store_id=store_id,
                           user_id=store.user_id)
        session.add(newItem)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newItem.name))
        return redirect(url_for('showMenu', store_id=store_id))
    else:
        return render_template('newmenuitem.html', store_id=store_id)

# Edit a menu item


@app.route('/store/<int:store_id>/menu/<int:menu_id>/edit',
           methods=['GET', 'POST'])
@login_required
def editMenuItem(store_id, menu_id):
    editedItem = session.query(MenuItem).filter_by(id=menu_id).one()
    store = session.query(Store).filter_by(id=store_id).one()
    if login_session['user_id'] != store.user_id:
        return "<h2>You do not have permission."\
            "Only the user who created store can edit</h2>"
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit()
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', store_id=store_id))
    else:
        return render_template('editmenuitem.html',
                               store_id=store_id,
                               menu_id=menu_id, item=editedItem)


# Delete a menu item
@app.route('/store/<int:store_id>/menu/<int:menu_id>/delete',
           methods=['GET', 'POST'])
@login_required
def deleteMenuItem(store_id, menu_id):
    store = session.query(Store).filter_by(id=store_id).one()
    itemToDelete = session.query(MenuItem).filter_by(id=menu_id).one()
    if login_session['user_id'] != store.user_id:
        return "<h2>You do not have permission."\
            "Only the user who created store can delete</h2>"
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', store_id=store_id))
    else:
        return render_template('deleteMenuItem.html', item=itemToDelete)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
