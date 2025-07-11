import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_portfolio = db.execute("SELECT id, symbol, name, SUM(shares) FROM trades WHERE id = ? GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY price DESC",
                                session["user_id"])
    user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    current_worth = 0

    for stocks in user_portfolio:
        stock_data = lookup(stocks["symbol"])
        stocks["currentprice"] = stock_data["price"]
        stocks["totalprice"] = stock_data["price"] * stocks["SUM(shares)"]
        current_worth += stocks["totalprice"]

    return render_template("index.html", user_portfolio=user_portfolio, user_cash=user_cash, current_worth=current_worth)


def is_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares_nbr = request.form.get("shares")

        # Ensure symbol is not blank
        if symbol == "":
            return apology("MISSING SYMBOL", 400)
        if shares_nbr == "" or shares_nbr.isalpha():
            return apology("MISSING SHARES", 400)
        if not is_int(shares_nbr):
            return apology("fractional not supported", 400)
        if int(shares_nbr) <= 0:
            return apology("share number can't be negative number or zero!", 400)

        stock_quote = lookup(symbol)

        if not stock_quote:
            return apology("INVALID SYMBOL", 400)

        total_cost = int(shares_nbr) * stock_quote["price"]

        user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        if user_cash[0]["cash"] < total_cost:
            return apology("CAN'T AFFORD", 400)

        else:
            db.execute("INSERT INTO trades (id, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?)",
                       session["user_id"], stock_quote['symbol'], stock_quote['name'], int(shares_nbr), stock_quote['price'])
            cash = user_cash[0]["cash"]
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       cash - total_cost, session["user_id"])
            flash('Bought!')
            return redirect("/")

    # User reached route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_transactions = db.execute(
        "SELECT id, symbol, shares, price, transacted FROM trades WHERE id = ? ORDER BY transacted", session["user_id"])
    return render_template("history.html", user_transactions=user_transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if symbol == "":
            return apology("input is blank", 400)

        stock_info = lookup(symbol)
        if not stock_info:
            return apology("INVALID SYMBOL", 400)
        else:
            return render_template("quoted.html", symbol=stock_info)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if not (password == confirmation):
            return apology("the password do not match", 400)

        if username == "" or password == "" or confirmation == "":
            return apology("input is blanck", 400)

        if len(rows) == 1:
            return apology("username alresdy exist", 400)
        else:
            hashcode = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashcode)

        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if symbol == "":
            return apology("MISSING SYMBOL", 400)
        if shares == "" or shares.isalpha():
            return apology("MISSING SHARES", 400)
        if not is_int(shares):
            return apology("fractional not supported", 400)
        if int(shares) <= 0:
            return apology("share number can't be negative number or zero!", 400)

        stock_quote = lookup(symbol)

        if not stock_quote:
            return apology("INVALID SYMBOL", 400)
        user_portfolio = db.execute(
            "SELECT id, symbol, SUM(shares) FROM trades WHERE id = ? AND symbol = ? GROUP BY symbol HAVING SUM(shares)>0 ", session["user_id"], stock_quote['symbol'])
        user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        if user_portfolio[0]["SUM(shares)"] < int(shares):
            return apology("TOO MANY SHARES", 400)
        else:
            # update user_portfolio with based on sell transaction info

            currentprice = stock_quote['price'] * int(shares)
            cash = user_cash[0]["cash"]
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       cash + currentprice, session["user_id"])
            db.execute("INSERT INTO trades (id, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?)",
                       session["user_id"], stock_quote['symbol'], stock_quote['name'], -int(shares), stock_quote['price'])
            flash('Sold!')
        return redirect("/")

    # User reached route via GET
    else:
        user_portfolio = db.execute(
            "SELECT id, symbol, SUM(shares) FROM trades WHERE id = ? GROUP BY symbol HAVING SUM(shares)>0 ORDER BY symbol", session["user_id"])

        return render_template("sell.html", user_portfolio=user_portfolio)


@app.route("/changepassword", methods=["GET", "POST"])
@login_required
def changepassword():
    # Create new password

    if request.method == "POST":

        currentpassword = request.form.get("currentpassword")
        newpassword = request.form.get("newpassword")
        confirmation = request.form.get("confirmation")

        rows = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        if currentpassword == "" or newpassword == "" or confirmation == "":
            return apology("input is blank", 400)

        if not check_password_hash(rows[0]["hash"], currentpassword):
            return apology("invalid password", 403)

        else:
            hashcode = generate_password_hash(newpassword, method='pbkdf2:sha256', salt_length=8)
            db.execute("UPDATE users SET hash = ? WHERE id = ?", hashcode, session["user_id"])

        return redirect("/settings")

    return render_template("changepassword.html")
