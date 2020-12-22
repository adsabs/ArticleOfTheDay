import os
import sys
import time
from flask_script import Manager, Command, Option
from app import create_app
from AoD import generate_batch
from AoD import post_article
from utils import post_to_slack

app = create_app()
# instantiate the manager object
manager = Manager(app)

class GenerateBatch(Command):

    def run(self, **kwargs):
        with create_app().app_context():
            resp = generate_batch()
            # If 'resp' has a key 'Slack' we have to send
            # a message to Slack
            if 'Slack' in resp:
                error_message = {
                    'text': resp['Slack'],
                    'link_names': 1
                }
                try:
                    slack = post_to_slack(error_message)
                except:
                    current_app.logger.exception("Failed to post to Slack")

class PostArticle(Command):

    def run(self, **kwargs):
        with create_app().app_context():
            resp = post_article()
            # If 'resp' has a key 'Slack' we have to send
            # a message to Slack
            if 'Slack' in resp:
                error_message = {
                    'text': resp['Slack'],
                    'link_names': 1
                }
                try:
                    slack = post_to_slack(error_message)
                except:
                    current_app.logger.exception("Failed to post to Slack")
                

manager.add_command('generate', GenerateBatch())
manager.add_command('post', PostArticle())

if __name__ == '__main__':
    manager.run()
