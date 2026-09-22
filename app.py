from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///movies.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer)
    watched = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Movie {self.title}>"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/movies")
def movies():
    movie_list = Movie.query.all()
    return render_template("movies.html", heading="My Movies", movies=movie_list)


@app.route("/movies/add", methods=["GET", "POST"])
def add_movie():
    if request.method == "POST":
        title = request.form["title"]
        year = request.form["year"]

        new_movie = Movie(title=title, year=int(year) if year else None)
        db.session.add(new_movie)
        db.session.commit()

        return redirect(url_for("movies"))

    return render_template("add_movie.html")

@app.route("/movies/<int:movie_id>/edit", methods = ["GET", "POST"])
def edit_movie(movie_id):
    movie = Movie.query.get(movie_id)
    if request.method == "POST":
        movie.title = request.form["title"]
        year = request.form["year"]
        movie.year = int(year) if year else None
        movie.watched = "watched" in request.form

        db.session.commit()
        return redirect(url_for("movies"))

    return render_template("edit_movie.html", movie=movie)

@app.route("/movies/<int:movie_id>/delete", methods=["POST"])
def delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    return redirect(url_for("movies"))



@app.route("/about")
def about():
    return render_template("about.html")




if __name__ == "__main__":
    app.run(debug=True)