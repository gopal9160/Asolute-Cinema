from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me-later"


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///movies.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

@app.context_processor
def inject_user():
    user_id = session.get("user_id")
    current_user = None
    if user_id:
        current_user = db.session.get(User, user_id)
    return {"current_user": current_user}


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer)
    watched = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    def __repr__(self):
        return f"<Movie {self.title}>"

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/signup", methods=["GET", "POST"])

def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        existing = User.query.filter_by(username=username).first()
        if existing:
            return "Username already exists. <a href='/signup'>Try again!</a>"

        new_user = User(username=username, password_hash=generate_password_hash(password))

        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id

        return redirect(url_for("movies"))

    return render_template("signup.html")




@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            return redirect(url_for("movies"))

        return "Invalid username or password. <a href='/login'>Try again</a>"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("movies"))


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/movies")
@login_required
def movies():
    movie_list = Movie.query.filter_by(user_id=session["user_id"]).all()
    return render_template("movies.html", heading="My Movies", movies=movie_list)


@app.route("/movies/add", methods=["GET", "POST"])
@login_required
def add_movie():
    if request.method == "POST":
        title = request.form["title"]
        year = request.form["year"]

        new_movie = Movie(title=title, year=int(year) if year else None, user_id=session["user_id"])
        db.session.add(new_movie)
        db.session.commit()

        return redirect(url_for("movies"))

    return render_template("add_movie.html")


@app.route("/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@login_required
def edit_movie(movie_id):
    movie = Movie.query.filter_by(id=movie_id, user_id=session["user_id"]).first_or_404()

    if request.method == "POST":
        movie.title = request.form["title"]
        year = request.form["year"]
        movie.year = int(year) if year else None
        movie.watched = "watched" in request.form

        db.session.commit()
        return redirect(url_for("movies"))

    return render_template("edit_movie.html", movie=movie)


@app.route("/movies/<int:movie_id>/delete", methods=["POST"])
@login_required
def delete_movie(movie_id):
    movie = Movie.query.filter_by(id=movie_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(movie)
    db.session.commit()
    return redirect(url_for("movies"))


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)