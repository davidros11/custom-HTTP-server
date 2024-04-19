# Custom HTTP Server

Custom HTTP server.

Has the following API Endpoints:

POST /login: Logs in. Body should contain a JSON object with the fields "UserName" and "Password".

POST /logout: logs out.

GET / : Returns "Welcome" in text

POST /: saves any uploaded files. Anything else is printed to stdout. Requires login
