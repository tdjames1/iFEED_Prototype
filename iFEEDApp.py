'''
iFEEDApp.py:

This module was developed by CEMAC ...................
Example:
    To use::
        python manage.py

Attributes:

.. CEMAC_iFEED:
   https://github.com/cemac/iFEED_prototype
'''


from flask import Flask, render_template, flash, redirect, url_for, request
from flask import g, session, abort, make_response
from wtforms import Form, validators, StringField, SelectField, TextAreaField
from wtforms import IntegerField, PasswordField, SelectMultipleField, widgets
import sqlite3
import pandas as pd
import numpy as np
import os
import io
import json
from passlib.hash import sha256_crypt
# Modules for this site
from access import *


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('home.html.j2')

# Access ----------------------------------------------------------------------

# Login
@app.route('/login', methods=["GET", "POST"])
def login():
    if 'logged_in' in session:
        flash('Already logged in', 'warning')
        return redirect(url_for('index'))
    if request.method == 'POST':
        # Get form fields
        username = request.form['username']
        password_candidate = request.form['password']
        user_login(username, password_candidate, conn)
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('login.html.j2')


# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('index'))


# Change password
@app.route('/change-pwd', methods=["GET", "POST"])
@is_logged_in
def change_pwd():
    username = session['username']
    form = ChangePwdForm(request.form)
    if request.method == 'POST' and form.validate():
        user = pd.read_sql_query("SELECT * FROM users where username is '"
                                 + username + "' ;", conn)
        password = user.password[0]
        current = form.current.data
        if sha256_crypt.verify(current, password):
            user.password = sha256_crypt.hash(str(form.new.data))
            sql = "UPDATE users SET password = ? WHERE username is ? ;"
            cur = conn.cursor()
            cur.execute(sql, (user.password[0], str(username)))
            conn.commit()
            flash('Password changed', 'success')
            return redirect(url_for('change_pwd'))
        else:
            flash('Current password incorrect', 'danger')
            return redirect(url_for('change_pwd'))
    return render_template('change-pwd.html.j2', form=form)


# Access settings for a given user
@app.route('/account/<string:username>', methods=['GET', 'POST'])
@is_logged_in
def account(username):
    role = session['usertype']
    # display role
    # user name
    # potential to add affiliations and email to give more bespoke access to
    # who can edit which volcanoes. Eg. Prject or Institute
    return render_template('account.html.j2', username=username, Role=role)

# Additional logged in as Admin only pages ------------------------------


@app.route('/admin/information', methods=['GET', 'POST'])
@is_logged_in_as_admin
def admininfo():
    return render_template('admininfo.html.j2')


@app.route('/admin/users', methods=['GET', 'POST'])
@is_logged_in_as_admin
def ViewOrAddUsers():
    df = pd.read_sql_query("SELECT * FROM Users ;", conn)
    df['password'] = '********'
    # add roles
    u2r = pd.read_sql_query("SELECT * FROM users_roles ;", conn)
    roles = pd.read_sql_query("SELECT * FROM roles ;", conn)
    u2r2 = pd.merge(u2r, roles, on='group_id')
    del u2r2['group_id']
    usersandroles = pd.merge(df, u2r2, on='id', how='outer')
    usersandroles.rename(columns={'name': 'Role'}, inplace=True)
    usersandroles = usersandroles.dropna(subset=['username'])
    colnames = [s.replace("_", " ").title() for s in usersandroles.columns.values[1:]]
    return render_template('view.html.j2', title='Users', colnames=colnames,
                           tableClass='Users', editLink="edit",
                           data=usersandroles)


# Add entry
@app.route('/add/Users', methods=["GET", "POST"])
@is_logged_in_as_admin
def add():
    form = eval("Users_Form")(request.form)
    if request.method == 'POST' and form.validate():
        # Get form fields:
        # Check
        if len(str(form.password.data)) < 8:
            return flash('password must be more than 8 characters',
                         'danger')
        form.password.data = sha256_crypt.hash(str(form.password.data))
        formdata = []
        for f, field in enumerate(form):
            formdata.append(field.data)
        InsertUser(formdata[0], formdata[1], conn)
        flash('User Added', 'success')
        return redirect(url_for('add', tableClass='Users'))
    return render_template('add.html.j2', title='Add Users', tableClass='Users',
                           form=form)


# Delete entry
@app.route('/delete/<string:tableClass>/<string:id>', methods=['POST'])
@is_logged_in_as_admin
def delete(tableClass, id):
    # Retrieve DB entry:
    user = pd.read_sql_query("SELECT * FROM Users where id = " + id + " ;",
                             conn)
    username = user.username
    DeleteUser(username[0], conn)
    flash('User Deleted', 'success')
    return redirect(url_for('ViewOrAddUsers'))


# Access settings for a given user
@app.route('/access/<string:id>', methods=['GET', 'POST'])
@is_logged_in_as_admin
def access(id):
    form = AccessForm(request.form)
    form.Role.choices = table_list('roles', 'name', conn)[1:]
    # Retrieve user DB entry:
    user = pd.read_sql_query("SELECT * FROM Users where id = " + id + " ;",
                             conn)
    if user.empty:
        abort(404)
    # Retrieve all current role
    u2r = pd.read_sql_query("SELECT * FROM users_roles WHERE id = " + id +
                            ";", conn)
    gid = u2r.group_id[0]
    current_role = pd.read_sql_query("SELECT * FROM roles WHERE group_id = "
                                     + str(gid) + ";", conn)
    # If user submits edit entry form:
    if request.method == 'POST' and form.validate():
        new_role = form.Role.data
        AssignRole(user.username[0], new_role, conn)
        print('test')
        # Return with success
        flash('Edits successful', 'success')
        return redirect(url_for('ViewOrAddUsers'))
    # Pre-populate form fields with existing data:
    form.username.render_kw = {'readonly': 'readonly'}
    form.username.data = user.username[0]
    form.Role.data = current_role.name[0]
    return render_template('access.html.j2', form=form, id=id)

# static information pages ---------------------------------------------------

@app.route('/copyright', methods=["GET"])
def copyright():
    return render_template('copyright.html.j2')

@app.route('/privacy', methods=["GET"])
def privacy():
    return render_template('privacy.html.j2')

@app.route('/contribute', methods=["GET"])
def contribute():
    return render_template('contributor_guidelines.html.j2')

@app.route('/about', methods=["GET"])
def about():
    return render_template('about.html.j2')


@app.route('/contact', methods=["GET"])
def contact():
    return render_template('contact.html.j2')

@app.route('/glossary', methods=["GET"])
def glossary():
    return render_template('glossary.html.j2')

# Error Pages ----------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html.j2'), 404


@app.errorhandler(403)
def page_not_found(e):
    # note that we set the 403 status explicitly
    return render_template('403.html.j2'), 403


@app.errorhandler(500)
def internal_error(error):
    app.logger.error('Server Error: %s', (error))
    return render_template('500.html.j2'), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error('Unhandled Exception: %s', (e))
    return render_template('500.html.j2'), 500


if __name__ == '__main__':
    app.run(host='129.11.85.32', debug=True, port=5900)
    #app.run(debug=True)
