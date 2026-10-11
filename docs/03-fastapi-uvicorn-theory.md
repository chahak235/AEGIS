# Theory: FastAPI and Uvicorn

- Web framework = library that does the repetitive web work (routing, validation, errors, docs).
- FastAPI = API-focused Python framework, built on Starlette (web) + Pydantic (data validation).
- Chosen for: auto validation, auto docs, type hints, async, speed.
- Alternatives: Flask (minimal), Django (batteries included), Express, Spring Boot, Gin.
- Uvicorn = ASGI server. It listens on the port and passes requests to FastAPI.
- WSGI = old sync contract, ASGI = new async contract.
- Async = serve other users while waiting (database, network).
- Alternatives to Uvicorn: Hypercorn, Daphne, Gunicorn.
- /docs (Swagger), /redoc, /openapi.json are generated automatically.
