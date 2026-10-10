from functools import wraps
import os
import requests

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-key")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///movies.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer)
    watched = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    poster_url = db.Column(db.String(500), nullable=True)
    tmdb_id = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"<Movie {self.title}>"


@app.context_processor
def inject_user():
    user_id = session.get("user_id")
    current_user = None
    if user_id:
        current_user = db.session.get(User, user_id)
    return {"current_user": current_user}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ---------- Auth routes ----------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("signup"))

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash("Username already taken.", "error")
            return redirect(url_for("signup"))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
        )
        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id
        flash(f"Welcome, {username}!", "success")
        return redirect(url_for("movies"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for("movies"))

        flash("Invalid username or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You've been logged out.", "success")
    return redirect(url_for("movies"))


# ---------- Public routes ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- Movie routes ----------

@app.route("/movies")
@login_required
def movies():
    query = request.args.get("q", "").strip()
    base_query = Movie.query.filter_by(user_id=session["user_id"])

    if query:
        movie_list = base_query.filter(Movie.title.ilike(f"%{query}%")).all()
    else:
        movie_list = base_query.all()

    return render_template("movies.html", heading="My Movies", movies=movie_list, query=query)


@app.route("/movies/add", methods=["GET", "POST"])
@login_required
def add_movie():
    if request.method == "POST":
        title = request.form["title"].strip()
        year = request.form["year"].strip()

        errors = []

        if not title:
            errors.append("Title is required.")

        if year:
            if not year.isdigit():
                errors.append("Year must be a number.")
            elif int(year) < 1888 or int(year) > 2100:
                errors.append("Year must be between 1888 and 2100.")

        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("add_movie"))

        new_movie = Movie(
            title=title,
            year=int(year) if year else None,
            user_id=session["user_id"],
        )
        db.session.add(new_movie)
        db.session.commit()

        flash("Movie added!", "success")
        return redirect(url_for("movies"))

    return render_template("add_movie.html")


# ---------- TMDB Search ----------

@app.route("/search", methods=["GET", "POST"])
@login_required
def search_movies():
    results = []
    query = ""

    if request.method == "POST":
        query = request.form.get("q", "").strip()

        if query:
            api_key = os.environ.get("TMDB_API_KEY")
            if not api_key:
                flash("Movie search is not configured.", "error")
                return redirect(url_for("search_movies"))

            url = "https://api.themoviedb.org/3/search/movie"
            params = {
                "api_key": api_key,
                "query": query,
                "include_adult": "false",
            }

            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                for item in data.get("results", [])[:12]:
                    poster_path = item.get("poster_path")
                    results.append({
                        "tmdb_id": item["id"],
                        "title": item.get("title") or item.get("name") or "Untitled",
                        "year": (item.get("release_date") or "")[:4] or None,
                        "poster_url": f"https://image.tmdb.org/t/p/w300{poster_path}" if poster_path else None,
                        "overview": (item.get("overview") or "")[:200],
                    })

            except requests.RequestException as e:
                flash("Could not reach movie database. Try again later.", "error")
                print(f"TMDB error: {e}")

    return render_template("search_movies.html", results=results, query=query)



@app.route("/api/search")
@login_required
def api_search():
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return {"results": []}

    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        return {"results": [], "error": "not configured"}

    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": api_key,
        "query": query,
        "include_adult": "false",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"TMDB error: {e}")
        return {"results": [], "error": "network"}

    results = []
    for item in data.get("results", [])[:20]:
        poster_path = item.get("poster_path")
        results.append({
            "tmdb_id": item["id"],
            "title": item.get("title") or item.get("name") or "Untitled",
            "year": (item.get("release_date") or "")[:4] or None,
            "poster_url": f"https://image.tmdb.org/t/p/w200{poster_path}" if poster_path else None,
            "overview": (item.get("overview") or "")[:300],
            "rating": round(item.get("vote_average") or 0, 1),
            "votes": item.get("vote_count") or 0,
            "popularity": item.get("popularity") or 0,
            "language": (item.get("original_language") or "").upper(),
        })

    # Sort by popularity — famous movies first
    results.sort(key=lambda m: m["popularity"], reverse=True)

    return {"results": results}


@app.route("/search/add", methods=["POST"])
@login_required
def add_from_search():
    title = request.form.get("title", "").strip()
    year = request.form.get("year", "").strip()
    poster_url = request.form.get("poster_url", "").strip()
    tmdb_id = request.form.get("tmdb_id", "").strip()

    if not title:
        flash("Invalid movie.", "error")
        return redirect(url_for("search_movies"))

    existing = Movie.query.filter_by(
        user_id=session["user_id"],
        title=title,
    ).first()

    if existing:
        flash(f"'{title}' is already in your watchlist.", "error")
        return redirect(url_for("search_movies"))

    new_movie = Movie(
        title=title,
        year=int(year) if year and year.isdigit() else None,
        user_id=session["user_id"],
        poster_url=poster_url or None,
        tmdb_id=int(tmdb_id) if tmdb_id and tmdb_id.isdigit() else None,
    )
    db.session.add(new_movie)
    db.session.commit()

    flash(f"Added '{title}' to your watchlist!", "success")
    return redirect(url_for("movies"))


# ---------- Edit / Delete ----------

@app.route("/movies/<int:movie_id>/edit", methods=["GET", "POST"])
@login_required
def edit_movie(movie_id):
    movie = Movie.query.filter_by(id=movie_id, user_id=session["user_id"]).first_or_404()

    if request.method == "POST":
        title = request.form["title"].strip()
        year = request.form["year"].strip()

        errors = []

        if not title:
            errors.append("Title is required.")

        if year:
            if not year.isdigit():
                errors.append("Year must be a number.")
            elif int(year) < 1888 or int(year) > 2100:
                errors.append("Year must be between 1888 and 2100.")

        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for("edit_movie", movie_id=movie_id))

        movie.title = title
        movie.year = int(year) if year else None
        movie.watched = "watched" in request.form

        db.session.commit()
        flash("Movie updated!", "success")
        return redirect(url_for("movies"))

    return render_template("edit_movie.html", movie=movie)


@app.route("/movies/<int:movie_id>/delete", methods=["POST"])
@login_required
def delete_movie(movie_id):
    movie = Movie.query.filter_by(id=movie_id, user_id=session["user_id"]).first_or_404()
    db.session.delete(movie)
    db.session.commit()

    flash("Movie deleted.", "success")
    return redirect(url_for("movies"))


# ---------- Error Handlers ----------

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=True)