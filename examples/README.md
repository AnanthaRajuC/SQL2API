# Examples

Try SQL2API against the bundled SQLite databases:

~~~bash
cd examples
cp db_connections.example.json db_connections.json
sql2api serve
~~~

Then, from another terminal:

~~~bash
# ad-hoc SQL
curl -X POST 'http://127.0.0.1:5000/execute_sql?page_size=3' -H 'Content-Type: application/json' \
     -d '{"sql": "SELECT * FROM actor", "connection_name": "sakila-sqlite"}'

# a saved query served as an endpoint - extra query-string arguments are bound as parameters
curl 'http://127.0.0.1:5000/q/actor_by_id?id=7'
curl 'http://127.0.0.1:5000/q/films_by_rating?rating=PG&max_length=60&format=csv'
curl 'http://127.0.0.1:5000/q/films_by_rating?rating=XX'   # 400: rating must be one of: G, PG, PG-13, R, NC-17
~~~

Every run of a saved query is appended to that version's `execution_history` (last 50 kept), so running these
examples modifies the files in `saved_sql/`.

Interactive API docs are at <http://127.0.0.1:5000/docs>.

## Contents

| File | What it is |
|------|------------|
| `db_connections.example.json` | Connection registry template. The two SQLite connections work out of the box; the rest are inactive templates that read passwords from environment variables. |
| `saved_sql/` | Two saved queries. `actor_by_id` has two versions; the latest one runs by default (`?version=1` selects the first). `films_by_rating` shows parameter rules: a default, allowed values and a numeric range. |
| `sqlite-sakila.db`, `chinook.db` | Sample SQLite databases derived from the [Sakila](https://dev.mysql.com/doc/sakila/en/) and [Chinook](https://github.com/lerocha/chinook-database) sample datasets. Check those projects' licences before redistributing them. |
