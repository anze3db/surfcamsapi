default:
    @just --list

server:
    uv run manage.py runserver 8003
