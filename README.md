<!--
*** Thanks for checking out Spring Boot Application Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Thanks again!
-->
# SQL2API

SQL2API is a middleware solution that bridges the gap between SQL databases and REST APIs. The system accepts SQL queries through HTTP endpoints and executes them against configured database connections, returning results in multiple formats including JSON, XML, YAML, CSV, TSV, and XLSX.

| Database      | JSON | XML | YAML| CSV |  TSV | XLSX |
|---------------|------|-----|-----|-----|------|------|
| MySQL         | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |
| Postgres      | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |
| ClickHouse    | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |
| H2            | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |
| SQLite        | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |

## Quick start

~~~bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd code
python SQL2API.py            # http://127.0.0.1:5000
~~~

~~~bash
curl -X POST 'http://localhost:5000/execute_sql?format=csv&page=1&page_size=5' \
     -H 'Content-Type: application/json' \
     -d '{"sql": "SELECT * FROM actor", "connection_name": "localhost-sqlite"}'
~~~

Run the tests from the `code` folder with `python -m unittest discover -s tests -t .`.

## Features

**Executing SQL Queries:** POST the SQL and a connection name to `/execute_sql`. Results are paginated (`page`, `page_size`) and returned in the format given by `format` (json, csv, tsv, xml, yaml, xlsx).

**Query Parameterization:** Saved queries can contain `{placeholders}`. Values are supplied in the request body when executing via `/execute_sql_with_parameters_from_file`; they must be numbers, booleans or plain text, so they cannot break out of the query.

**Saving and Versioning Queries:** PATCH `/save_sql_to_file` stores a query with metadata (author, description, tags). Saving under an existing filename adds a new version; executing a saved query always runs the latest version.

**Listing Saved Queries:** GET `/list_files` returns every saved query with its versions and metadata, and can be sorted with `sort_by` and `sort_order`.

**Connection Management:** GET `/connections` lists the configured connections (passwords are masked) and PATCH `/connections` adds or updates them.

## Safe by default

SQL2API runs whatever SQL it is given, so it ships locked down. All of this is configured with environment variables:

| Variable | Default | Effect |
|----------|---------|--------|
| `SQL2API_ALLOW_WRITES` | off | Only single, read-only statements (`SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`) are accepted. Set to `1` to allow `INSERT`/`UPDATE`/DDL. |
| `SQL2API_API_KEY` | unset | When set, every request must carry a matching `X-API-Key` header. |
| `SQL2API_MAX_PAGE_SIZE` | `1000` | Upper limit for `page_size`. |
| `SQL2API_HOST` / `SQL2API_PORT` | `127.0.0.1` / `5000` | Address the server binds to. |
| `SQL2API_DEBUG` | off | Flask debug mode. Never enable on a network-reachable host. |

Saved-query files can only be read from the `code/saved_sql` folder, and passwords in `db_connections.json` are never returned by the API. Even so, do not expose the service to untrusted networks without an API key and a reverse proxy in front of it.

---  

<div align="center">

[![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen?logo=github)](CODE_OF_CONDUCT.md) [![Tweet](https://img.shields.io/twitter/url/http/shields.io.svg?style=social)](https://twitter.com/intent/tweet?text=Checkout+this+sql+to+api+application&url=https://github.com/AnanthaRajuC/SQL2API&hashtags=Python) [![Twitter Follow](https://img.shields.io/twitter/follow/anantharajuc?label=follow%20me&style=social)](https://twitter.com/anantharajuc)
</div>

<div align="center">
  <sub>Built with ❤︎ by <a href="https://twitter.com/anantharajuc">Anantha Raju C</a> and <a href="https://github.com/AnanthaRajuC/SQL2API/graphs/contributors">contributors</a>
</div>

</br>

<p align="center">
	<a href="https://github.com/AnanthaRajuC/SQL2API/blob/master/README.md#spring-boot-application-templatestarter-project-"><strong>Explore the docs »</strong></a>
	<br />
	<br />
	<a href="https://github.com/AnanthaRajuC/SQL2API/issues">Report Bug</a>
	·
	<a href="https://github.com/AnanthaRajuC/SQL2API/issues">Request Feature</a>
</p>

<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
-->

|     Service     | Badge | Badge | Badge | Badge | Badge |
|-----------------|-------|-------|-------|-------|-------|
|  **GitHub**     |[![GitHub last commit](https://img.shields.io/github/last-commit/AnanthaRajuC/SQL2API)](https://github.com/AnanthaRajuC/SQL2API/commits/master)|[![GitHub pull requests](https://img.shields.io/github/issues-pr-raw/AnanthaRajuC/SQL2API)](https://github.com/AnanthaRajuC/SQL2API/pulls)|[![GitHub issues](https://img.shields.io/github/issues/AnanthaRajuC/SQL2API)](https://github.com/AnanthaRajuC/SQL2API/issues)|[![GitHub forks](https://img.shields.io/github/forks/AnanthaRajuC/SQL2API)](https://github.com/AnanthaRajuC/SQL2API/network)|[![GitHub stars](https://img.shields.io/github/stars/AnanthaRajuC/SQL2API)](https://github.com/AnanthaRajuC/SQL2API/stargazers)|
|  **GitHub**     |![GitHub repo size](https://img.shields.io/github/repo-size/AnanthaRajuC/SQL2API)|![GitHub top language](https://img.shields.io/github/languages/top/AnanthaRajuC/SQL2API.svg)|![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/AnanthaRajuC/SQL2API)|![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/AnanthaRajuC/SQL2API.svg)|![GitHub language count](https://img.shields.io/github/languages/count/AnanthaRajuC/SQL2API)|


## Reporting Issues/Suggest Improvements

This Project uses GitHub's integrated issue tracking system to record bugs and feature requests. If you want to raise an issue, please follow the recommendations below:

* 	Before you log a bug, please [search the issue tracker](https://github.com/AnanthaRajuC/SQL2API/search?type=Issues) to see if someone has already reported the problem.
* 	If the issue doesn't already exist, [create a new issue](https://github.com/AnanthaRajuC/SQL2API/issues/new)
* 	Please provide as much information as possible with the issue report.
* 	If you need to paste code, or include a stack trace use Markdown +++```+++ escapes before and after your text.

<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

Kindly refer to [CONTRIBUTING.md](/CONTRIBUTING.md) for important **Pull Request Process** details

1. In the top-right corner of this page, click **Fork**.

2. Clone a copy of your fork on your local, replacing *YOUR-USERNAME* with your Github username.

   `git clone https://github.com/YOUR-USERNAME/SQL2API.git`

3. **Create a branch**: 

   `git checkout -b <my-new-feature-or-fix>`

4. **Make necessary changes and commit those changes**:

   `git add .`

   `git commit -m "new feature or fix"`

5. **Push changes**, replacing `<add-your-branch-name>` with the name of the branch you created earlier at step #3. :

   `git push origin <add-your-branch-name>`

6. Submit your changes for review. Go to your repository on GitHub, you'll see a **Compare & pull request** button. Click on that button. Now submit the pull request.

That's it! Soon I'll be merging your changes into the master branch of this project. You will get a notification email once the changes have been merged. Thank you for your contribution.

Kindly follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) to create an explicit commit history. Kindly prefix the commit message with one of the following type's.

**build**   : Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)  
**ci**      : Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)  
**docs**    : Documentation only changes  
**feat**    : A new feature  
**fix**     : A bug fix  
**perf**    : A code change that improves performance  
**refactor**: A code change that neither fixes a bug nor adds a feature  
**style**   : Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)  
**test**    : Adding missing tests or correcting existing tests  

## The End

In the end, I hope you enjoyed the application and find it useful, as I did when I was developing it.

If you would like to enhance, please: 

* 	**Open PRs**, 
* 	Give **feedback**, 
* 	Add **new suggestions**, and
*	Finally, give it a 🌟.

* Happy Coding ...* 🙂

<!-- CONTACT -->
## Contact

Anantha Raju C - [@anantharajuc](https://twitter.com/anantharajuc) - arcswdev@gmail.com

Project Link: [https://github.com/AnanthaRajuC/SQL2API](https://github.com/AnanthaRajuC/SQL2API)



