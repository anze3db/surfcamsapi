default:
    @just --list

server:
    uv run manage.py runserver 8003

worker:
    uv run manage.py potatoq worker
