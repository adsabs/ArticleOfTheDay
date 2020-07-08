import click
import os
import sys
import time
from flask_script import Manager, Command, Option
from app import create_app
from AoD import generate_batch
from AoD import post_article

app = create_app()
# instantiate the manager object
manager = Manager(app)

class GenerateBatch(Command):

    def run(self, **kwargs):
        with create_app().app_context():
            res = generate_batch()

class PostArticle(Command):

    def run(self, **kwargs):
        with create_app().app_context():
            res = post_article()

manager.add_command('generate', GenerateBatch())
manager.add_command('post', PostArticle())

if __name__ == '__main__':
    manager.run()
