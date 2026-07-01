# https://www.youtube.com/watch?v=qF5il_9IwME&t=17s


1. So help me set up a checklist here in the @docs/todo.md  file. What is the most logical way to set up this project? Do we start with a back end or front end? Give me a checklist that I can work toward to implement this project.

    * run linter: 

    uv run ruff check .
    uv run ruff format .

        uv run ruff check app tests
        uv run ruff format app tests


2. Hey, You are going to help me work on the to-do list. Go to phase #1. We need to set up the app config.py. Can you set up that scaffold?

 
    * Run locally from backend/:

      uv run uvicorn app.main:app --reload

3.  Can you now create a @backend/app/main.py  file and see if we can actually import this?
