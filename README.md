<!--
*** Thanks for checking out Spring Boot Application Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Thanks again!
-->
# SQL2API

This project is a Flask-based application designed for executing SQL queries against multiple database types and retrieving the results in various formats.

|---------------|------|-----|-----|-----|------|------|
| Database      | JSON | XML | YAML| CSV |  TSV | XLSX |
|---------------|------|-----|-----|-----|------|------|
| MySQL         | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |
| Postgres      | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |
| ClickHouse    | ✅   | ✅  | ✅  | ✅  | ✅   | ✅   |

**Executing SQL Queries:** Users can execute SQL queries by sending POST requests to the '/execute_sql' endpoint of the application. They need to provide the SQL query and the connection name as part of the request body.

**Query Parameterization:** The application supports query parameterization by allowing users to specify placeholders in their SQL queries. Placeholder values can be provided as part of the request body when executing the query.

**Saving and Managing Queries:** Users can save SQL queries along with metadata such as author, description, and tags by sending PATCH requests to the '/save_sql_to_file' endpoint. They can also manage saved queries, including editing and deleting them.

**Listing Saved Queries:** Users can list the saved queries stored in the application by sending GET requests to the '/list_files' endpoint. The endpoint returns a list of filenames along with versioning information and metadata for each saved query.

**Connection Management:** Users can manage database connections by sending PATCH requests to the '/connections' endpoint. They can add, edit, or delete connection details, including host, port, username, password, and database name.

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



