# Lesson 2: main.py explained

- import = bring in a library's tool
- app = FastAPI(...) = create the application object
- @app.get("/path") = decorator: link a GET address to a function
- def = function, indentation matters
- return {..} = dictionary, FastAPI converts it to JSON
- Uvicorn runs the server; FastAPI holds the rules; --reload restarts on save
- 404 = address not defined, 500 = bug in code
