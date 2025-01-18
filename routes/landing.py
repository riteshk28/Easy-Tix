from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Tenant, User
from werkzeug.security import generate_password_hash

landing = Blueprint('landing', __name__)

@landing.route('/')
def index():
    return render_template('landing/index.html')

@landing.route('/contact', methods=['POST'])
def contact():
    # Here you would typically handle the contact form submission
    # For now, we'll just flash a message
    flash('Thank you for your interest! We will contact you soon.')
    return redirect(url_for('landing.index')) 